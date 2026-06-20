from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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
    step_limit: int | None = None
    timeout_seconds: float | None = None
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


class ProverTimeoutError(RuntimeError):
    """Raised when prover setup crosses its time budget."""


class Prover:
    def run(
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
                    proof_payload = on_proof_found(
                        ProofFound(
                            problem=problem,
                            strategy_index=strategy_index,
                            strategy=entry.strategy,
                            result=result,
                            state=closed_state,
                        )
                    )
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
        deadline = self._deadline(entry.timeout_seconds)
        steps = 0
        inference_actions = 0
        state: State | None = None
        try:
            state = self._build_state_from_file(
                problem,
                matrix_options=strategy.matrix,
                matrix_cache=matrix_cache,
                deadline=deadline,
            )
            policy = strategy.policy.instantiate()
            steps, inference_actions, outcome = self._run_strategy_loop(
                state,
                policy=policy,
                step_limit=entry.step_limit,
                timeout_seconds=self._remaining_seconds(deadline),
            )
        except ProverTimeoutError:
            outcome = ProverOutcome.TIMEOUT
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
            step_limit=entry.step_limit,
            timeout_seconds=entry.timeout_seconds,
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
        timeout_seconds: float | None,
    ) -> tuple[int, int, ProverOutcome | None]:
        deadline = self._deadline(timeout_seconds)
        if deadline is not None and time.monotonic() >= deadline:
            return 0, 0, ProverOutcome.TIMEOUT

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
            if deadline is not None and time.monotonic() >= deadline:
                outcome = ProverOutcome.TIMEOUT
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
        deadline: float | None,
    ) -> State:
        if self._deadline_reached(deadline):
            raise ProverTimeoutError("strategy timed out before state construction")

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
        if self._deadline_reached(deadline):
            raise ProverTimeoutError("strategy timed out during state construction")
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

    @staticmethod
    def _deadline(timeout_seconds: float | None) -> float | None:
        if timeout_seconds is None:
            return None
        return time.monotonic() + timeout_seconds

    @staticmethod
    def _remaining_seconds(deadline: float | None) -> float | None:
        if deadline is None:
            return None
        return max(0.0, deadline - time.monotonic())

    @staticmethod
    def _deadline_reached(deadline: float | None) -> bool:
        return deadline is not None and time.monotonic() >= deadline

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
