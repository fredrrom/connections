"""What runs produce, and the one serialization contract for it.

``Result.to_dict`` is the data contract between connections and anything built
on it, versioned by the ``schema`` field. Trajectories serialize with replay
identity: the position each action was taken at, enough for ``resolve_record``
to regenerate the action against a replayed state. Transitions are
deterministic, so the record sequence and a fresh initial state reconstruct
the derivation; instance ids are allocated at replay time and are recorded
only as provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

from connections.agent.base import AgentStatus
from connections.calculus.actions import Action, ApplyAction, UndoAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import Extension, Factorization, Reduction, Start
from connections.calculus.state import State
from connections.interaction.outcome import ProverOutcome
from connections.interaction.szs import SZSStatus

RESULT_SCHEMA = "connections.result.v1"

StrategyT = TypeVar("StrategyT")


class Stop(Enum):
    """Why the rollout loop ended: its own observation.

    ``AGENT_DONE`` is the only stop that consults the agent, and the only one
    for which ``Rollout.status`` is set.
    """

    AGENT_DONE = "agent_done"
    STEP_BUDGET = "step_budget"
    TIME_BUDGET = "time_budget"


@dataclass(frozen=True, slots=True)
class Rollout:
    """What a rollout did, and why it stopped.

    ``steps`` is counted whether or not actions are recorded; when they are,
    equality of the two is enforced here.
    """

    state: State
    stop: Stop
    status: AgentStatus | None
    actions: tuple[Action, ...] | None
    steps: int

    def __post_init__(self) -> None:
        if self.actions is not None and len(self.actions) != self.steps:
            raise ValueError("recorded actions disagree with the step count")


@dataclass(frozen=True, slots=True)
class StrategyResult(Generic[StrategyT]):
    strategy: StrategyT
    outcome: ProverOutcome | None
    steps: int
    proof_size: int
    elapsed_seconds: float
    szs_status: SZSStatus | None = None
    agent_status: AgentStatus | None = None
    trajectory: tuple[Action, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": None if self.outcome is None else self.outcome.value,
            "szs_status": None if self.szs_status is None else self.szs_status.value,
            "agent_status": None
            if self.agent_status is None
            else self.agent_status.value,
            "steps": self.steps,
            "proof_size": self.proof_size,
            "elapsed_seconds": self.elapsed_seconds,
            "trajectory": None
            if self.trajectory is None
            else [action_record(action) for action in self.trajectory],
        }


@dataclass(frozen=True, slots=True)
class Result(Generic[StrategyT]):
    outcome: ProverOutcome | None
    strategy_results: tuple[StrategyResult[StrategyT], ...]
    winning_strategy_index: int | None = None
    szs_status: SZSStatus | None = None
    proof_payload: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """The serialization contract, versioned by ``schema``.

        Facts about the execution -- host, wall time, provenance -- are the
        caller's to add around this, not fields of it.
        """
        return {
            "schema": RESULT_SCHEMA,
            "outcome": None if self.outcome is None else self.outcome.value,
            "szs_status": None if self.szs_status is None else self.szs_status.value,
            "winning_strategy_index": self.winning_strategy_index,
            "strategy_results": [r.to_dict() for r in self.strategy_results],
        }


def action_record(action: Action) -> dict[str, Any]:
    """One action as replay identity: kind and position."""
    if isinstance(action, UndoAction):
        return {"kind": "undo", "step_id": action.step_id}
    rule = action.rule
    if isinstance(rule, Start):
        return {
            "kind": "start",
            "goal_id": action.goal_id,
            "clause_idx": rule.clause_idx,
            "instance_id": rule.instance_id,
        }
    if isinstance(rule, Extension):
        return {
            "kind": "extension",
            "goal_id": action.goal_id,
            "clause_idx": rule.clause_idx,
            "lit_idx": rule.lit_idx,
            "instance_id": rule.instance_id,
        }
    if isinstance(rule, Reduction):
        return {
            "kind": "reduction",
            "goal_id": action.goal_id,
            "source_goal_id": rule.source_goal_id,
        }
    if isinstance(rule, Factorization):
        return {
            "kind": "factorization",
            "goal_id": action.goal_id,
            "source_goal_id": rule.source_goal_id,
            "mode": rule.mode,
        }
    raise TypeError(f"unrecordable action: {action!r}")


def resolve_record(state: State, record: dict[str, Any]) -> Action | None:
    """Regenerate the recorded action against the current state.

    Position identifies the action; the constraint delta and instance id are
    recomputed, since the transition function is deterministic and instance
    numbering depends on generation order, not on the derivation.
    """
    kind = record["kind"]
    if kind == "undo":
        return UndoAction(step_id=record["step_id"])
    goal_id = record["goal_id"]
    if kind == "start":
        for mode in ("positive", "conjecture"):
            for rule in Dynamics.start_rules_for(state, mode):
                if rule.clause_idx == record["clause_idx"]:
                    return ApplyAction(goal_id, rule)
        return None
    if kind == "extension":
        return Dynamics.extension_action_for_position(
            state,
            goal_id,
            record["clause_idx"],
            record["lit_idx"],
            instance_id=state.fresh_instance_id(),
        )
    if kind == "reduction":
        for rule in Dynamics.reduction_rules_for(state, goal_id):
            if rule.source_goal_id == record["source_goal_id"]:
                return ApplyAction(goal_id, rule)
        return None
    if kind == "factorization":
        for rule in Dynamics.factorization_rules_for(
            state, goal_id, mode=record["mode"]
        ):
            if rule.source_goal_id == record["source_goal_id"]:
                return ApplyAction(goal_id, rule)
        return None
    raise ValueError(f"unknown action record kind: {kind!r}")


__all__ = [
    "RESULT_SCHEMA",
    "Result",
    "Rollout",
    "Stop",
    "StrategyResult",
    "action_record",
    "resolve_record",
]
