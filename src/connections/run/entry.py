"""One problem, one result.

Named ``entry`` rather than ``run`` because a submodule ``connections.run.run``
would shadow the ``run`` function: Python binds a submodule as an attribute of
its package, and that lookup wins before any lazy export in ``__init__``. The
public name is ``connections.run.run``; this module is where it is defined.

``run`` is the highest entry point ``connections`` has. It handles a single
problem, in the calling process, with no notion of other problems and no
opinion about how many should be in flight. That is where CASC draws the line
too -- systems there run "as black boxes, on one problem at a time" -- so
running many is not a bigger ``run``, it is many runs, and arranging them
belongs to whoever owns the machine.

Configuration is passed at the call and every cache lives for its duration.
Holding it as instance state instead would cost thread-safety, an invalidation
rule for a second call with a different schedule, and a lifecycle, and buy
almost nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from connections.calculus.outcome import ProverOutcome
from connections.calculus.state import State
from connections.calculus.tableau import Tableau
from connections.clausification import matrix_from_file
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Matrix
from connections.run.limits import (
    WallClockExceeded,
    _memory_limit,
    _wall_clock_alarm,
)
from connections.run.result import Result, StrategyResult
from connections.run.rollout import rollout
from connections.run.strategy import (
    MatrixOptions,
    ScheduledStrategy,
    Strategy,
    StrategySchedule,
)
from connections.run.szs import SZSStatus, to_szs_status

StrategyT = TypeVar("StrategyT", bound=Strategy)
ProofFoundCallback = Callable[["ProofFound[StrategyT]"], Any]

MatrixCache = dict[tuple[object, ...], Matrix]


@dataclass(frozen=True, slots=True)
class ProblemSpec:
    """A problem as a file plus the context needed to read it.

    Source directories are part of the call. Nothing here reads ``TPTP``,
    ``ILTP`` or ``QMLTP`` from the environment, which is what lets a run be
    reproduced on a machine configured differently from the one that recorded
    it.
    """

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
class ProofFound(Generic[StrategyT]):
    problem: ProblemSpec
    strategy_index: int
    strategy: StrategyT
    result: StrategyResult[StrategyT]
    state: State


@dataclass(frozen=True, slots=True)
class _StrategyRun(Generic[StrategyT]):
    result: StrategyResult[StrategyT]
    proof_state: State | None = None


def run(
    problem: ProblemSpec,
    *,
    schedule: StrategyT | StrategySchedule[StrategyT],
    on_proof_found: ProofFoundCallback[StrategyT] | None = None,
    memory_limit_mb: int | None = None,
) -> Result[StrategyT]:
    """Turn one problem into one result.

    Builds a state per strategy in the schedule, instantiates that strategy's
    policy, rolls out under its share of the budget, and stops at the first
    success.
    """

    with _memory_limit(memory_limit_mb):
        return _run_schedule(
            problem,
            schedule=schedule,
            on_proof_found=on_proof_found,
        )


def build_state(
    problem: ProblemSpec,
    *,
    matrix_options: MatrixOptions,
    matrix_cache: MatrixCache | None = None,
) -> State:
    """Where a file becomes a state.

    This is the one place ``run`` reaches down past the calculus into parsing
    and clausification: read the file, clausify it into a matrix, wrap it as
    the initial state of *P(M)*.
    """

    matrix = _matrix_from_file(
        problem,
        matrix_options=matrix_options,
        matrix_cache=matrix_cache,
    )
    return State(matrix=matrix, tableau=Tableau())


def _run_schedule(
    problem: ProblemSpec,
    *,
    schedule: StrategyT | StrategySchedule[StrategyT],
    on_proof_found: ProofFoundCallback[StrategyT] | None = None,
) -> Result[StrategyT]:
    schedule = _strategy_schedule(schedule)
    strategy_results: list[StrategyResult[StrategyT]] = []
    winning_strategy_index: int | None = None
    outcome: ProverOutcome | None = None
    szs_status: SZSStatus | None = None
    proof_payload: Any | None = None
    matrix_cache: MatrixCache = {}

    for strategy_index, entry in enumerate(schedule.entries):
        strategy_run = _run_strategy(
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
                # The proof callback shares the strategy's wall-clock budget:
                # search already consumed elapsed_seconds, and an unbounded
                # callback would otherwise turn a proved problem into a
                # supervisor-level timeout.
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

    return Result(
        outcome=outcome,
        strategy_results=tuple(strategy_results),
        winning_strategy_index=winning_strategy_index,
        szs_status=szs_status,
        proof_payload=proof_payload,
    )


def _strategy_schedule(
    schedule: StrategyT | StrategySchedule[StrategyT],
) -> StrategySchedule[StrategyT]:
    if isinstance(schedule, StrategySchedule):
        return schedule
    return StrategySchedule.single(schedule)


def _run_strategy(
    problem: ProblemSpec,
    *,
    entry: ScheduledStrategy[StrategyT],
    matrix_cache: MatrixCache | None = None,
) -> _StrategyRun[StrategyT]:
    strategy = entry.strategy
    outcome: ProverOutcome | None = None
    started_at = time.monotonic()
    steps = 0
    inference_actions = 0
    state: State | None = None
    try:
        with _wall_clock_alarm(entry.timeout_seconds):
            state = build_state(
                problem,
                matrix_options=strategy.matrix,
                matrix_cache=matrix_cache,
            )
            policy = strategy.policy.instantiate()
            attempt = rollout(
                state,
                policy=policy,
                step_limit=entry.step_limit,
                deadline=(
                    None
                    if entry.timeout_seconds is None
                    else started_at + entry.timeout_seconds
                ),
            )
            outcome = attempt.outcome
            steps = attempt.steps
            inference_actions = attempt.inference_steps
    except WallClockExceeded:
        outcome = ProverOutcome.TIMEOUT
    except MemoryError:
        outcome = ProverOutcome.MEMORY_OUT
    has_conjecture = None if state is None else state.matrix.source_has_conjecture
    result = StrategyResult(
        strategy=strategy,
        outcome=outcome,
        steps=steps,
        inference_actions=inference_actions,
        elapsed_seconds=time.monotonic() - started_at,
        szs_status=to_szs_status(outcome, has_conjecture=has_conjecture),
    )
    return _StrategyRun(
        result=result,
        proof_state=state if outcome is ProverOutcome.PROVED else None,
    )


def _matrix_from_file(
    problem: ProblemSpec,
    *,
    matrix_options: MatrixOptions,
    matrix_cache: MatrixCache | None,
) -> Matrix:
    matrix_key = (
        None
        if matrix_cache is None
        else _matrix_cache_key(problem, matrix_options=matrix_options)
    )
    if matrix_key is not None and matrix_cache is not None:
        cached = matrix_cache.get(matrix_key)
        if cached is not None:
            return cached

    matrix = matrix_from_file(
        problem.path,
        translation=matrix_options.translation,
        reorder=matrix_options.reorder,
        mark_conjecture=matrix_options.mark_conjecture,
        logic=problem.logic,
        domain=problem.domain,
        source_file_dirs=problem.source_file_dirs,
    )

    if matrix_key is not None and matrix_cache is not None:
        matrix_cache[matrix_key] = matrix
    return matrix


def _matrix_cache_key(
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
        matrix_options.mark_conjecture,
    )


__all__ = [
    "ProblemSpec",
    "ProofFound",
    "ProofFoundCallback",
    "build_state",
    "run",
]
