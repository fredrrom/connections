from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Generic, Iterable, Protocol, Sequence, TypeAlias, TypeVar, cast

from connections.clausification import StartClausesMode, matrix_from_file
from connections.core.logic import Domain, Logic
from connections.core.matrix import Matrix
from connections.core.status import ProverOutcome, SZSStatus, to_szs_status
from connections.policy import Policy
from connections.prover.actions import Action, ActionChoice, ApplyAction
from connections.prover.dynamics import Dynamics
from connections.prover.state import State
from connections.prover.strategy import (
    MatrixOptions,
    ScheduledStrategy,
    StrategySchedule,
    WeightedStrategy,
)
from connections.prover.tableau import Tableau
from connections.trace_logging import trace, trace_logger


class _Strategy(Protocol):
    matrix: MatrixOptions

    def create_policy(self) -> Policy: ...


StrategyT = TypeVar("StrategyT", bound=_Strategy)
_StrategyArg: TypeAlias = (
    StrategyT
    | WeightedStrategy[StrategyT]
    | ScheduledStrategy[StrategyT]
    | Sequence[StrategyT | WeightedStrategy[StrategyT] | ScheduledStrategy[StrategyT]]
)


@dataclass(frozen=True, slots=True)
class _ProblemInput:
    path: str | Path
    logic: Logic = "classical"
    domain: Domain = "constant"
    source_file_dirs: tuple[str | Path, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_file_dirs", tuple(self.source_file_dirs))


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


class ProverHook:
    def on_strategy_start(
        self,
        strategy_index: int,
        entry: ScheduledStrategy[Any],
    ) -> None:
        return None

    def on_choice(self, state: State, choice: ActionChoice) -> None:
        return None

    def on_transition(self, state: State, action: Action) -> None:
        return None

    def on_proof_found(self, state: State) -> None:
        return None

    def on_strategy_end(
        self,
        result: StrategyResult[Any],
        state: State | None,
    ) -> None:
        return None


class ProverTimeoutError(RuntimeError):
    """Raised when prover setup crosses its time budget."""


class Prover:
    def run(
        self,
        problem: str | Path,
        *,
        strategy: _StrategyArg[StrategyT] | None = None,
        schedule: StrategySchedule[StrategyT] | None = None,
        logic: Logic = "classical",
        domain: Domain = "constant",
        source_file_dirs: Sequence[str | Path] = (),
        hooks: Iterable[ProverHook] = (),
    ) -> ProverResult[StrategyT]:
        problem_input = _ProblemInput(
            problem,
            logic=logic,
            domain=domain,
            source_file_dirs=tuple(source_file_dirs),
        )
        schedule = self._normalize_schedule(schedule=schedule, strategy=strategy)
        strategy_results: list[StrategyResult[StrategyT]] = []
        winning_strategy_index: int | None = None
        outcome: ProverOutcome | None = None
        szs_status: SZSStatus | None = None
        matrix_cache: dict[tuple[object, ...], Matrix] = {}
        hooks_tuple = tuple(hooks)

        for strategy_index, entry in enumerate(schedule.entries):
            result = self._run_strategy(
                problem_input,
                entry=entry,
                matrix_cache=matrix_cache,
                strategy_index=strategy_index,
                hooks=hooks_tuple,
            )
            strategy_results.append(result)
            outcome = result.outcome
            szs_status = result.szs_status
            if outcome is ProverOutcome.PROVED:
                winning_strategy_index = strategy_index
                break

        return ProverResult(
            outcome=outcome,
            strategy_results=tuple(strategy_results),
            winning_strategy_index=winning_strategy_index,
            szs_status=szs_status,
        )

    def _normalize_schedule(
        self,
        *,
        schedule: StrategySchedule[StrategyT] | None,
        strategy: _StrategyArg[StrategyT] | None,
    ) -> StrategySchedule[StrategyT]:
        if schedule is not None and strategy is not None:
            raise ValueError("pass either schedule or strategy, not both")
        if schedule is not None:
            return schedule
        if strategy is None:
            raise ValueError("pass strategy or schedule")

        if isinstance(strategy, ScheduledStrategy):
            return StrategySchedule(entries=(strategy,))
        if isinstance(strategy, WeightedStrategy):
            return StrategySchedule.from_weighted((strategy,))
        if not isinstance(strategy, Sequence):
            return StrategySchedule.single(strategy)

        normalized = tuple(strategy)
        if not normalized:
            return StrategySchedule(entries=())
        if all(isinstance(strategy, ScheduledStrategy) for strategy in normalized):
            return StrategySchedule(
                entries=cast(tuple[ScheduledStrategy[StrategyT], ...], normalized)
            )
        if any(isinstance(strategy, ScheduledStrategy) for strategy in normalized):
            raise ValueError("do not mix scheduled strategies with unscheduled strategies")

        weighted_entries = tuple(
            strategy
            if isinstance(strategy, WeightedStrategy)
            else WeightedStrategy(strategy=strategy)
            for strategy in normalized
        )
        return StrategySchedule.from_weighted(weighted_entries)

    def _run_strategy(
        self,
        problem: _ProblemInput,
        *,
        entry: ScheduledStrategy[StrategyT],
        matrix_cache: dict[tuple[object, ...], Matrix] | None = None,
        strategy_index: int = 0,
        hooks: tuple[ProverHook, ...] = (),
    ) -> StrategyResult[StrategyT]:
        strategy = entry.strategy
        outcome: ProverOutcome | None = None
        for hook in hooks:
            hook.on_strategy_start(strategy_index, entry)
        started_at = time.monotonic()
        deadline = self._deadline(entry.timeout_seconds)
        inference_actions = 0
        state: State | None = None
        try:
            state = self._build_state_from_file(
                problem,
                matrix_options=strategy.matrix,
                matrix_cache=matrix_cache,
                deadline=deadline,
            )
            policy = strategy.create_policy()
            inference_actions, outcome = self._run_strategy_loop(
                state,
                policy=policy,
                step_limit=entry.step_limit,
                timeout_seconds=self._remaining_seconds(deadline),
                hooks=hooks,
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
            inference_actions=inference_actions,
            elapsed_seconds=time.monotonic() - started_at,
            step_limit=entry.step_limit,
            timeout_seconds=entry.timeout_seconds,
            szs_status=szs_status,
        )
        for hook in hooks:
            hook.on_strategy_end(result, state)
        return result

    def _run_strategy_loop(
        self,
        state: State,
        *,
        policy: Policy,
        step_limit: int | None,
        timeout_seconds: float | None,
        hooks: tuple[ProverHook, ...],
    ) -> tuple[int, ProverOutcome | None]:
        deadline = self._deadline(timeout_seconds)
        if deadline is not None and time.monotonic() >= deadline:
            return 0, ProverOutcome.TIMEOUT

        outcome: ProverOutcome | None = None
        inference_actions = 0
        while outcome is None:
            if state.tableau.root.closed and state.constraints.satisfiable(
                logic=state.problem.logic,
                domain=state.problem.domain,
            ):
                outcome = self._record_proof_found(state, hooks, policy=policy)
                break
            if deadline is not None and time.monotonic() >= deadline:
                outcome = ProverOutcome.TIMEOUT
                break

            output = policy(state)
            if isinstance(output, ProverOutcome):
                outcome = output
                break
            if output is None:
                break
            choice = output
            action = choice.action

            if isinstance(action, ApplyAction):
                if step_limit is not None and inference_actions >= step_limit:
                    outcome = ProverOutcome.STEP_BUDGET
                    break
                inference_actions += 1

            if hooks:
                for hook in hooks:
                    hook.on_choice(state, choice)
            Dynamics.transition(state, action)
            trace(trace_logger, action.trace_event())
            if hooks:
                for hook in hooks:
                    hook.on_transition(state, action)
            if (
                state.tableau.root.closed
                and outcome is None
                and state.constraints.satisfiable(
                    logic=state.problem.logic,
                    domain=state.problem.domain,
                )
            ):
                outcome = self._record_proof_found(state, hooks, policy=policy)

        return inference_actions, outcome

    def _record_proof_found(
        self,
        state: State,
        hooks: tuple[ProverHook, ...],
        *,
        policy: Policy | None = None,
    ) -> ProverOutcome:
        if policy is not None:
            policy.record_proof_found(state)
        for hook in hooks:
            hook.on_proof_found(state)
        return ProverOutcome.PROVED

    def _build_state_from_file(
        self,
        problem: _ProblemInput,
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
        problem: _ProblemInput,
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
        problem: _ProblemInput,
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
    "Prover",
    "ProverHook",
    "ProverResult",
    "StrategyResult",
]
