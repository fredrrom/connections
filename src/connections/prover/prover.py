from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import logging
import signal
import time
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from connections.clausification import StartClausesMode, matrix_from_file
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Matrix
from connections.prover.status import ProverOutcome, SZSStatus, to_szs_status
from connections.policy import DFSPolicy, Policy
from connections.prover.actions import Action, ApplyAction
from connections.prover.dynamics import Dynamics
from connections.prover.state import State
from connections.prover.strategy import (
    MatrixOptions,
    ScheduledStrategy,
    Strategy,
    StrategySchedule,
)
from connections.prover.tableau import Tableau
from connections.trace_logging import trace, trace_logger


StrategyT = TypeVar("StrategyT", bound=Strategy)
ProofFoundCallback = Callable[["ProofFound[StrategyT]"], Any]


@dataclass(frozen=True, slots=True)
class ProblemSpec:
    path: str | Path
    logic: Logic = "classical"
    domain: Domain = "constant"
    source_file_dirs: tuple[str | Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(
            self,
            "source_file_dirs",
            tuple(Path(directory) for directory in self.source_file_dirs),
        )


@dataclass(frozen=True, slots=True)
class Problem:
    matrix: Matrix
    start_clauses: StartClausesMode
    logic: Logic = "classical"
    domain: Domain = "constant"
    start_clause_ids: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.start_clauses == "conjecture":
            start_clause_ids = (
                self.matrix.conjecture_clauses or self.matrix.positive_clauses
            )
            object.__setattr__(self, "start_clause_ids", start_clause_ids)
            return
        object.__setattr__(self, "start_clause_ids", self.matrix.positive_clauses)

    @property
    def has_conjecture(self) -> bool:
        return bool(self.matrix.source_has_conjecture)


@dataclass(frozen=True, slots=True)
class StrategyResult(Generic[StrategyT]):
    strategy: StrategyT
    outcome: ProverOutcome | None
    steps: int
    inference_actions: int
    elapsed_seconds: float
    szs_status: SZSStatus | None = None


@dataclass(frozen=True, slots=True)
class ProverResult(Generic[StrategyT]):
    outcome: ProverOutcome | None
    strategy_results: tuple[StrategyResult[StrategyT], ...]
    winning_strategy_index: int | None = None
    szs_status: SZSStatus | None = None
    proof_payload: Any | None = None


@dataclass(frozen=True, slots=True)
class _StrategyRun(Generic[StrategyT]):
    result: StrategyResult[StrategyT]
    proof_state: State | None = None


@dataclass(frozen=True, slots=True)
class ProofFound(Generic[StrategyT]):
    problem: ProblemSpec
    strategy_index: int
    strategy: StrategyT
    result: StrategyResult[StrategyT]
    state: State


class WallClockExceeded(BaseException):
    """Raised by the SIGALRM handler; BaseException so policy code with broad
    `except Exception` handlers cannot swallow it."""


@contextmanager
def _wall_clock_alarm(seconds: float | None):
    """Enforce a wall-clock budget over the enclosed block via SIGALRM.

    The prover self-limits the way E does with --cpu-limit: the OS interrupts
    the attempt wherever it is (parsing, clausification, search) and the
    signal handler raises. Requires the main thread; when signals are
    unavailable (non-main thread, non-POSIX) the budget is not enforced and
    external supervision must cover it. Nested use is unsupported: the
    enclosed block must not arm ITIMER_REAL itself.
    """

    if seconds is None or not hasattr(signal, "SIGALRM"):
        yield
        return
    if seconds <= 0:
        # setitimer(0) would disarm rather than fire; an exhausted budget
        # times out before any work happens.
        raise WallClockExceeded

    def _raise(_signum: int, _frame: Any) -> None:
        raise WallClockExceeded

    try:
        previous = signal.signal(signal.SIGALRM, _raise)
    except ValueError:  # not the main thread
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@contextmanager
def _memory_limit(limit_mb: int | None):
    """Best-effort process memory cap (E's --memory-limit analog).

    On Linux, lowering RLIMIT_AS makes a runaway allocation raise MemoryError
    at the failing allocation site, which the prover reports as MemoryOut.
    macOS rejects lowering memory rlimits, so there this is a no-op and only
    external supervision bounds memory.
    """

    if limit_mb is None:
        yield
        return
    try:
        import resource
    except ImportError:
        yield
        return
    res = getattr(resource, "RLIMIT_AS", None)
    if res is None:
        yield
        return
    try:
        soft, hard = resource.getrlimit(res)
        resource.setrlimit(res, (limit_mb * 1024**2, hard))
    except (ValueError, OSError):
        yield
        return
    try:
        yield
    finally:
        try:
            resource.setrlimit(res, (soft, hard))
        except (ValueError, OSError):
            # A failed restore leaves the process under the lowered cap;
            # surface it instead of failing silently.
            logging.getLogger(__name__).warning(
                "failed to restore RLIMIT_AS to (%d, %d)", soft, hard
            )


class Prover:
    def run(
        self,
        problem: ProblemSpec,
        *,
        schedule: StrategyT | StrategySchedule[StrategyT],
        on_proof_found: ProofFoundCallback[StrategyT] | None = None,
        memory_limit_mb: int | None = None,
    ) -> ProverResult[StrategyT]:
        with _memory_limit(memory_limit_mb):
            return self._run_schedule(
                problem,
                schedule=schedule,
                on_proof_found=on_proof_found,
            )

    def _run_schedule(
        self,
        problem: ProblemSpec,
        *,
        schedule: StrategyT | StrategySchedule[StrategyT],
        on_proof_found: ProofFoundCallback[StrategyT] | None = None,
    ) -> ProverResult[StrategyT]:
        schedule = self._strategy_schedule(schedule)
        strategy_results: list[StrategyResult[StrategyT]] = []
        winning_strategy_index: int | None = None
        outcome: ProverOutcome | None = None
        szs_status: SZSStatus | None = None
        proof_payload: Any | None = None
        matrix_cache: dict[tuple[object, ...], Matrix] = {}

        for strategy_index, entry in enumerate(schedule.entries):
            strategy_run = self._run_strategy(
                problem,
                entry=entry,
                matrix_cache=matrix_cache,
            )
            result = strategy_run.result
            strategy_results.append(result)
            outcome = result.outcome
            szs_status = result.szs_status
            if outcome is ProverOutcome.PROVED:
                winning_strategy_index = strategy_index
                closed_state = strategy_run.proof_state
                if on_proof_found is not None and closed_state is not None:
                    # The proof callback shares the strategy's wall-clock
                    # budget: search already consumed elapsed_seconds, and an
                    # unbounded callback would otherwise turn a proved problem
                    # into a supervisor-level timeout.
                    remaining = (
                        entry.timeout_seconds - result.elapsed_seconds
                        if entry.timeout_seconds is not None
                        else None
                    )
                    try:
                        with _wall_clock_alarm(remaining):
                            proof_payload = on_proof_found(
                                ProofFound(
                                    problem=problem,
                                    strategy_index=strategy_index,
                                    strategy=entry.strategy,
                                    result=result,
                                    state=closed_state,
                                )
                            )
                    except WallClockExceeded:
                        proof_payload = None
                break

        return ProverResult(
            outcome=outcome,
            strategy_results=tuple(strategy_results),
            winning_strategy_index=winning_strategy_index,
            szs_status=szs_status,
            proof_payload=proof_payload,
        )

    def _strategy_schedule(
        self,
        schedule: StrategyT | StrategySchedule[StrategyT],
    ) -> StrategySchedule[StrategyT]:
        if isinstance(schedule, StrategySchedule):
            return schedule
        return StrategySchedule.single(schedule)

    def _run_strategy(
        self,
        problem: ProblemSpec,
        *,
        entry: ScheduledStrategy[StrategyT],
        matrix_cache: dict[tuple[object, ...], Matrix] | None = None,
    ) -> _StrategyRun[StrategyT]:
        strategy = entry.strategy
        outcome: ProverOutcome | None = None
        started_at = time.monotonic()
        steps = 0
        inference_actions = 0
        state: State | None = None
        try:
            with _wall_clock_alarm(entry.timeout_seconds):
                state = self._build_state_from_file(
                    problem,
                    matrix_options=strategy.matrix,
                    matrix_cache=matrix_cache,
                )
                policy = strategy.policy.instantiate()
                steps, inference_actions, outcome = self._run_strategy_loop(
                    state,
                    policy=policy,
                    step_limit=entry.step_limit,
                )
        except WallClockExceeded:
            outcome = ProverOutcome.TIMEOUT
        except MemoryError:
            outcome = ProverOutcome.MEMORY_OUT
        has_conjecture = None if state is None else state.problem.has_conjecture
        szs_status = to_szs_status(
            outcome,
            has_conjecture=has_conjecture,
        )
        result = StrategyResult(
            strategy=strategy,
            outcome=outcome,
            steps=steps,
            inference_actions=inference_actions,
            elapsed_seconds=time.monotonic() - started_at,
            szs_status=szs_status,
        )
        return _StrategyRun(
            result=result,
            proof_state=state if outcome is ProverOutcome.PROVED else None,
        )

    def _run_strategy_loop(
        self,
        state: State,
        *,
        policy: Policy,
        step_limit: int | None,
    ) -> tuple[int, int, ProverOutcome | None]:
        outcome: ProverOutcome | None = None
        steps = 0
        inference_actions = 0
        while outcome is None:
            if state.tableau.root.closed and state.constraints.satisfiable(
                logic=state.problem.logic,
                domain=state.problem.domain,
            ):
                outcome = ProverOutcome.PROVED
                break
            if step_limit is not None and steps >= step_limit:
                outcome = ProverOutcome.STEP_BUDGET
                break

            output = cast(Action | ProverOutcome | None, policy(state))
            steps += 1
            if isinstance(output, ProverOutcome):
                outcome = output
                break
            if output is None:
                break
            action = output

            if isinstance(action, ApplyAction):
                inference_actions += 1

            Dynamics.transition(state, action)
            trace(trace_logger, action.trace_event())
            if (
                state.tableau.root.closed
                and outcome is None
                and state.constraints.satisfiable(
                    logic=state.problem.logic,
                    domain=state.problem.domain,
                )
            ):
                if isinstance(policy, DFSPolicy):
                    policy._on_tableau_closed(state)
                outcome = ProverOutcome.PROVED

        return steps, inference_actions, outcome

    def _build_state_from_file(
        self,
        problem: ProblemSpec,
        *,
        matrix_options: MatrixOptions,
        matrix_cache: dict[tuple[object, ...], Matrix] | None,
    ) -> State:
        matrix = self._matrix_from_file(
            problem,
            matrix_options=matrix_options,
            matrix_cache=matrix_cache,
        )
        state = State(
            problem=Problem(
                matrix=matrix,
                start_clauses=matrix_options.start_clauses,
                logic=problem.logic,
                domain=problem.domain,
            ),
            tableau=Tableau(),
        )
        return state

    def _matrix_from_file(
        self,
        problem: ProblemSpec,
        *,
        matrix_options: MatrixOptions,
        matrix_cache: dict[tuple[object, ...], Matrix] | None,
    ) -> Matrix:
        matrix_key = (
            None
            if matrix_cache is None
            else self._matrix_cache_key(
                problem,
                matrix_options=matrix_options,
            )
        )
        if matrix_key is not None:
            cached = matrix_cache.get(matrix_key) if matrix_cache is not None else None
            if cached is not None:
                return cached

        matrix = matrix_from_file(
            problem.path,
            translation=matrix_options.translation,
            reorder=matrix_options.reorder,
            start_clauses=matrix_options.start_clauses,
            logic=problem.logic,
            domain=problem.domain,
            source_file_dirs=problem.source_file_dirs,
        )

        if matrix_key is not None and matrix_cache is not None:
            matrix_cache[matrix_key] = matrix
        return matrix

    def _matrix_cache_key(
        self,
        problem: ProblemSpec,
        *,
        matrix_options: MatrixOptions,
    ) -> tuple[object, ...]:
        return (
            Path(problem.path).resolve(),
            problem.logic,
            problem.domain,
            tuple(Path(directory).resolve() for directory in problem.source_file_dirs),
            matrix_options.translation,
            matrix_options.reorder,
            matrix_options.start_clauses,
        )

__all__ = [
    "Domain",
    "Logic",
    "Problem",
    "ProofFound",
    "ProofFoundCallback",
    "ProblemSpec",
    "Prover",
    "ProverResult",
    "StrategyResult",
]
