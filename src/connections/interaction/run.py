"""Runs schedules and strategies: computes the agent function and reports.

One problem, one result. The prover formulates the matrix per strategy, rolls
the agent out under each entry's share of the budget, maps what came back to
SZS, and returns a Result.

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

from connections.agent import Agent
from connections.environment.state import State
from connections.environment.tableau import Tableau
from connections.clausification import matrix_from_file
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Matrix
from connections.interaction.records import Result, StrategyResult
from connections.interaction.rollout import rollout
from connections.interaction.strategy import (
    MatrixOptions,
    ScheduledStrategy,
    Strategy,
    StrategySchedule,
)
from connections.interaction.szs import DECIDED, SUCCESS, SZSStatus, to_szs_status

StrategyT = TypeVar("StrategyT", bound=Strategy)
ProofFoundCallback = Callable[["ProofFound[StrategyT]"], Any]

MatrixCache = dict[tuple[object, ...], Matrix]


@dataclass(frozen=True, slots=True)
class Problem:
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
    problem: Problem
    strategy_index: int
    strategy: StrategyT
    result: StrategyResult[StrategyT]
    state: State


@dataclass(frozen=True, slots=True)
class _StrategyRun(Generic[StrategyT]):
    result: StrategyResult[StrategyT]
    proof_state: State | None = None


def run_schedule(
    problem: Problem,
    *,
    schedule: StrategyT | StrategySchedule[StrategyT],
    agent: Agent | None = None,
    on_proof_found: ProofFoundCallback[StrategyT] | None = None,
    record_trajectory: bool = False,
) -> Result[StrategyT]:
    """Turn one problem into one result.

    Builds a state per strategy in the schedule, rolls out under that entry's
    share of the budget, and stops at the first success.

    Agent lifetime is the caller's choice. By default each entry instantiates
    a fresh agent from its strategy options, which is the frozen-theta
    evaluation protocol. Passing ``agent`` reuses one agent across every
    entry -- the deliberate exception for intra-conjecture work, where memory
    across attempts is the point. What carries over is then the agent's
    business, and any exhaustion claims remain per-episode.

    ``record_trajectory`` keeps each rollout's action sequence; off by
    default, since a corpus run has no reader for sixty thousand actions per
    problem.

    Budgets here are best effort: steps and seconds divide the schedule and
    are checked between rollout steps. connections imposes no wall-clock alarm
    and no memory cap on itself; a hard guarantee that a problem ends needs a
    supervising process that can kill this one, and that is where Timeout and
    MemoryOut verdicts come from.
    """

    schedule = _strategy_schedule(schedule)
    strategy_results: list[StrategyResult[StrategyT]] = []
    winning_strategy_index: int | None = None
    szs_status: SZSStatus | None = None
    proof_payload: Any | None = None
    matrix_cache: MatrixCache = {}
    agent_cache: dict[int, Agent] = {}

    for strategy_index, entry in enumerate(schedule.entries):
        strategy_run = run_strategy(
            problem,
            entry=entry,
            matrix_cache=matrix_cache,
            agent_cache=agent_cache,
            agent=agent,
            record_trajectory=record_trajectory,
        )
        result = strategy_run.result
        strategy_results.append(result)
        # A schedule aggregates by strength of verdict. A proof settles the
        # problem and stops the schedule. A countermodel from a systematic
        # strategy also settles it, but later strategies still get their turn
        # at a proof; a weaker verdict never overwrites it.
        if szs_status not in DECIDED or result.szs_status in SUCCESS:
            szs_status = result.szs_status
        if result.szs_status in SUCCESS:
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

    return Result(
        strategy_results=tuple(strategy_results),
        winning_strategy_index=winning_strategy_index,
        szs_status=szs_status,
        proof_payload=proof_payload,
    )


def build_state(
    problem: Problem,
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


def _strategy_schedule(
    schedule: StrategyT | StrategySchedule[StrategyT],
) -> StrategySchedule[StrategyT]:
    if isinstance(schedule, StrategySchedule):
        return schedule
    return StrategySchedule.single(schedule)


def _proof_size(state: State) -> int:
    """|s_T|: the rule applications the final derivation carries."""
    return len(state.tableau.rule_applications)


def run_strategy(
    problem: Problem,
    *,
    entry: ScheduledStrategy[StrategyT],
    matrix_cache: MatrixCache | None = None,
    agent_cache: dict[int, Agent] | None = None,
    agent: Agent | None = None,
    record_trajectory: bool = False,
) -> _StrategyRun[StrategyT]:
    strategy = entry.strategy
    started_at = time.monotonic()
    state = build_state(
        problem,
        matrix_options=strategy.matrix,
        matrix_cache=matrix_cache,
    )
    if agent is not None:
        acting = agent
    elif agent_cache is not None:
        # One agent per recipe within the run: the performance element
        # persists, and detects episode boundaries from the percept. What its
        # persistent strata carry across entries is the agent's business.
        key = id(strategy.policy)
        acting = agent_cache.get(key)
        if acting is None:
            acting = strategy.policy.instantiate()
            agent_cache[key] = acting
    else:
        acting = strategy.policy.instantiate()
    attempt = rollout(
        state,
        acting,
        record=record_trajectory,
        step_limit=entry.step_limit,
        deadline=(
            None
            if entry.timeout_seconds is None
            else started_at + entry.timeout_seconds
        ),
    )
    szs = to_szs_status(
        attempt.truncation,
        attempt.status,
        has_conjecture=state.matrix.source_has_conjecture,
    )
    result = StrategyResult(
        strategy=strategy,
        truncation=attempt.truncation,
        agent_status=attempt.status,
        trajectory=attempt.actions,
        steps=attempt.steps,
        proof_size=_proof_size(state) if szs in SUCCESS else 0,
        elapsed_seconds=time.monotonic() - started_at,
        szs_status=szs,
    )
    return _StrategyRun(
        result=result,
        proof_state=state if szs in SUCCESS else None,
    )


def _matrix_from_file(
    problem: Problem,
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
    problem: Problem,
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
    "Problem",
    "ProofFound",
    "ProofFoundCallback",
    "build_state",
    "run_schedule",
    "run_strategy",
]
