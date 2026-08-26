"""Experiments: run an agent over a corpus, and the measures over records.

This module is the research note as code. The loop is the experimenter's
sampling plan -- which problems, how many episodes per problem per pass,
what budgets -- and it knows nothing about learning: it asks the agent for
an actor per episode, runs the bare agent-environment loop, builds the
record, reports the outcome back, and ticks the agent once per wave.
Parallelism is an injected ``concurrent.futures`` executor; correctness of
running wide rests on the agent's frozen-theta contract, so a parallel run
equals a serial one.

The measures are identities over the records the loop produces, in the
note's vocabulary: an attempt tau has T = ``steps`` policy steps and ends
in the derivation s_T; ``proof_size`` is |s_T|; ``waste`` is
W(tau) = T - |s_T|, the exact regret against an oracle that knew which
derivation it was building; ``directness`` is |s_T| / T. All of it assumes
the attempt started from the empty derivation, which makes |s_T| <= T an
invariant rather than a convention, and all of it is placement-invariant:
steps are counted by the loop, wherever it executes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import Executor, as_completed
from dataclasses import dataclass
from typing import Any

from connections.agent import Agent, AgentStatus
from connections.interaction.records import Rollout, StrategyResult, action_record
from connections.interaction.rollout import rollout
from connections.interaction.run import Problem, build_state
from connections.interaction.strategy import MatrixOptions
from connections.interaction.szs import SUCCESS

from imitation.actor_learner import ActorLearnerAgent
from imitation.tasks import EpisodeTask

logger = logging.getLogger(__name__)

_PROGRESS_SECONDS = 10.0

# Measures: matrix-level quantities of one attempt, and their aggregates.


@dataclass(frozen=True, slots=True)
class AttemptMeasures:
    """One attempt's contribution to every matrix-level measure.

    ``proof_size``, ``directness`` and ``waste`` are ``None`` unless the
    attempt succeeded; ``directness`` is also ``None`` for a zero-step
    success, where the ratio is undefined. ``elapsed_seconds`` is ``None``
    when the record carries no timing, as a bare rollout does.
    """

    success: bool
    steps: int
    elapsed_seconds: float | None
    proof_size: int | None
    directness: float | None
    waste: int | None


@dataclass(frozen=True, slots=True)
class CorpusMeasures:
    """Aggregates over a set of attempts: J_S, J_T, J_L, J_D.

    The conditional measures are means over the successful attempts only
    and are ``None``, never NaN, when there are none. Reporting J_T and
    J_L gives the expected waste by subtraction; J_D does not follow from
    them, since the expectation of a ratio is not the ratio of
    expectations.
    """

    attempts: int
    successes: int
    j_s: float
    j_t: float | None
    j_l: float | None
    j_d: float | None


def _measures(
    *,
    success: bool,
    steps: int,
    proof_size: int,
    elapsed_seconds: float | None,
) -> AttemptMeasures:
    if not success:
        return AttemptMeasures(
            success=False,
            steps=steps,
            elapsed_seconds=elapsed_seconds,
            proof_size=None,
            directness=None,
            waste=None,
        )
    if proof_size > steps:
        raise ValueError(
            f"proof size {proof_size} exceeds steps {steps}: "
            "the attempt did not start from the empty derivation"
        )
    return AttemptMeasures(
        success=True,
        steps=steps,
        elapsed_seconds=elapsed_seconds,
        proof_size=proof_size,
        directness=proof_size / steps if steps else None,
        waste=steps - proof_size,
    )


def from_strategy_result(result: StrategyResult) -> AttemptMeasures:
    """Measures of one scheduled attempt; success is the SZS verdict."""

    return _measures(
        success=result.szs_status in SUCCESS,
        steps=result.steps,
        proof_size=result.proof_size,
        elapsed_seconds=result.elapsed_seconds,
    )


def from_rollout(attempt: Rollout) -> AttemptMeasures:
    """Measures of one bare rollout; success is the agent reporting closure.

    |s_T| is read off the final state as the number of rule applications
    standing in the tableau, which is the derivation the attempt built.
    """

    return _measures(
        success=attempt.status is AgentStatus.CLOSED,
        steps=attempt.steps,
        proof_size=len(attempt.state.tableau.rule_applications),
        elapsed_seconds=None,
    )


def aggregate(attempts: Iterable[AttemptMeasures]) -> CorpusMeasures:
    """J_S over all attempts; J_T, J_L, J_D over the successful ones."""

    collected = tuple(attempts)
    succeeded = tuple(a for a in collected if a.success)
    directed = tuple(a.directness for a in succeeded if a.directness is not None)
    return CorpusMeasures(
        attempts=len(collected),
        successes=len(succeeded),
        j_s=len(succeeded) / len(collected) if collected else 0.0,
        j_t=(
            sum(a.steps for a in succeeded) / len(succeeded) if succeeded else None
        ),
        j_l=(
            sum(a.proof_size or 0 for a in succeeded) / len(succeeded)
            if succeeded
            else None
        ),
        j_d=sum(directed) / len(directed) if directed else None,
    )


def success_curve(
    attempts: Sequence[AttemptMeasures],
    budgets: Sequence[int],
    *,
    run_budget: int,
) -> tuple[float, ...]:
    """J_S at every budget H' <= the budget the runs actually used.

    One run set determines the whole curve below its budget, because
    success is monotone in it: an attempt that closed after T transitions
    succeeds under every budget strictly greater than T -- the budget check
    precedes the call on which the agent observes closure, so a budget of
    exactly T truncates instead -- and one that found no proof under
    ``run_budget`` finds none under less. Asking about a budget beyond
    ``run_budget`` is an error, not an extrapolation.
    """

    for budget in budgets:
        if budget > run_budget:
            raise ValueError(
                f"budget {budget} exceeds the run budget {run_budget}: "
                "the runs carry no information beyond it"
            )
    if not attempts:
        return tuple(0.0 for _ in budgets)
    return tuple(
        sum(1 for a in attempts if a.success and a.steps < budget) / len(attempts)
        for budget in budgets
    )


# The loop: waves of episodes over the corpus, records made by the driver.


@dataclass(frozen=True, slots=True)
class EpisodeRecord:
    """One episode's outcome, with the proof when one was found."""

    problem_path: str
    pass_index: int
    trajectory_index: int
    measures: AttemptMeasures
    proof: tuple[dict[str, Any], ...] | None


@dataclass(frozen=True, slots=True)
class PassReport:
    pass_index: int
    records: tuple[EpisodeRecord, ...]

    @property
    def solved(self) -> int:
        return sum(1 for record in self.records if record.measures.success)


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    passes: tuple[PassReport, ...]
    steps_spent: int

    def records(self) -> tuple[EpisodeRecord, ...]:
        return tuple(record for report in self.passes for record in report.records)

    def proofs(self) -> dict[str, tuple[dict[str, Any], ...]]:
        """The first proof found per problem, in replayable form."""

        found: dict[str, tuple[dict[str, Any], ...]] = {}
        for record in self.records():
            if record.proof is not None and record.problem_path not in found:
                found[record.problem_path] = record.proof
        return found


def run_experiment(
    agent: ActorLearnerAgent,
    problems: Sequence[Problem],
    *,
    horizon: int | None,
    total_steps: int,
    episodes_per_problem: int = 1,
    timeout_seconds: float | None = None,
    executor: Executor | None = None,
    matrix: MatrixOptions | None = None,
) -> ExperimentReport:
    """Passes of episodes over the corpus until the budget or the agent ends.

    ``total_steps`` sums transitions across every episode and is checked at
    pass boundaries, so the last pass may overrun by at most one wave.
    More than one episode per problem per pass only earns its compute under
    a stochastic chooser.
    """

    matrix_options = matrix if matrix is not None else MatrixOptions()
    reports: list[PassReport] = []
    spent = 0
    pass_index = 0
    while True:
        tasks = tuple(
            EpisodeTask(
                problem=problem,
                round_index=pass_index,
                step_limit=horizon,
                timeout_seconds=timeout_seconds,
                trajectory_index=trajectory,
            )
            for problem in problems
            for trajectory in range(episodes_per_problem)
        )
        records = _run_wave(agent, tasks, matrix_options, executor)
        spent += sum(record.measures.steps for record in records)
        report = PassReport(pass_index=pass_index, records=records)
        reports.append(report)
        logger.info(
            "pass %d done: %d/%d solved, %d steps this pass, %d/%d total",
            pass_index,
            report.solved,
            len(records),
            sum(record.measures.steps for record in records),
            spent,
            total_steps,
        )
        pass_index += 1
        if spent >= total_steps:
            logger.info("stopping: total step budget spent")
            break
        if agent.halted:
            logger.info("stopping: the agent halted (a pass changed nothing)")
            break
    return ExperimentReport(passes=tuple(reports), steps_spent=spent)


def _run_wave(
    agent: ActorLearnerAgent,
    tasks: Sequence[EpisodeTask],
    matrix_options: MatrixOptions,
    executor: Executor | None,
) -> tuple[EpisodeRecord, ...]:
    progress = _WaveProgress(total=len(tasks))
    records = []
    if executor is None:
        for task in tasks:
            attempt = _episode(task, agent.subagent(task), matrix_options)
            record = _record(task, attempt)
            records.append(record)
            agent.observe_episode(task, attempt)
            progress.note(record)
    else:
        pending = {
            executor.submit(_episode, task, agent.subagent(task), matrix_options): task
            for task in tasks
        }
        for future in as_completed(pending):
            task = pending[future]
            attempt = future.result()
            record = _record(task, attempt)
            records.append(record)
            agent.observe_episode(task, attempt)
            progress.note(record)
    agent.wave_completed()
    return tuple(records)


class _WaveProgress:
    """Throttled running commentary on a wave, for long corpora."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.completed = 0
        self.solved = 0
        self.steps = 0
        self.started = time.monotonic()
        self.reported = self.started

    def note(self, record: EpisodeRecord) -> None:
        self.completed += 1
        self.steps += record.measures.steps
        if record.measures.success:
            self.solved += 1
        logger.debug(
            "pass %d episode %d/%d: %s %s in %d steps",
            record.pass_index,
            self.completed,
            self.total,
            record.problem_path.rsplit("/", 1)[-1],
            "solved" if record.measures.success else "unsolved",
            record.measures.steps,
        )
        now = time.monotonic()
        if now - self.reported >= _PROGRESS_SECONDS and self.completed < self.total:
            rate = self.completed / max(now - self.started, 1e-9)
            logger.info(
                "pass %d: %d/%d episodes, %d solved, %d steps, %.1f episodes/s",
                record.pass_index,
                self.completed,
                self.total,
                self.solved,
                self.steps,
                rate,
            )
            self.reported = now


def _episode(
    task: EpisodeTask, actor: Agent, matrix_options: MatrixOptions
) -> Rollout:
    state = build_state(task.problem, matrix_options=matrix_options)
    deadline = (
        None
        if task.timeout_seconds is None
        else time.monotonic() + task.timeout_seconds
    )
    return rollout(state, actor, step_limit=task.step_limit, deadline=deadline)


def _record(task: EpisodeTask, attempt: Rollout) -> EpisodeRecord:
    measures = from_rollout(attempt)
    proof = None
    if measures.success and attempt.actions is not None:
        proof = tuple(action_record(action) for action in attempt.actions)
    return EpisodeRecord(
        problem_path=str(task.problem.path),
        pass_index=task.round_index,
        trajectory_index=task.trajectory_index,
        measures=measures,
        proof=proof,
    )


# Analyses over reports: retention and evaluation.


def solved_by_pass(report: ExperimentReport) -> tuple[frozenset[str], ...]:
    """Which problems each pass solved: the raw material of retention."""

    return tuple(
        frozenset(
            record.problem_path
            for record in pass_report.records
            if record.measures.success
        )
        for pass_report in report.passes
    )


@dataclass(frozen=True, slots=True)
class Retention:
    """What changed between two consecutive passes' solved sets."""

    kept: frozenset[str]
    gained: frozenset[str]
    lost: frozenset[str]


def retention(report: ExperimentReport) -> tuple[Retention, ...]:
    """Per consecutive pass pair: proofs kept, gained, and forfeited."""

    solved = solved_by_pass(report)
    return tuple(
        Retention(
            kept=earlier & later,
            gained=later - earlier,
            lost=earlier - later,
        )
        for earlier, later in zip(solved, solved[1:])
    )


def evaluate(
    build: Callable[[], Agent],
    problems: Sequence[Problem],
    *,
    horizon: int | None,
    episodes_per_problem: int = 1,
    timeout_seconds: float | None = None,
    executor: Executor | None = None,
    matrix: MatrixOptions | None = None,
) -> ExperimentReport:
    """One effective pass of a frozen policy: the degenerate experiment."""

    agent = ActorLearnerAgent(lambda task: build())
    return run_experiment(
        agent,
        problems,
        horizon=horizon,
        total_steps=1,
        episodes_per_problem=episodes_per_problem,
        timeout_seconds=timeout_seconds,
        executor=executor,
        matrix=matrix,
    )


__all__ = [
    "AttemptMeasures",
    "CorpusMeasures",
    "EpisodeRecord",
    "ExperimentReport",
    "PassReport",
    "Retention",
    "aggregate",
    "evaluate",
    "from_rollout",
    "from_strategy_result",
    "retention",
    "run_experiment",
    "solved_by_pass",
    "success_curve",
]
