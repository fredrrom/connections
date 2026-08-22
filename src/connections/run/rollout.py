"""An agent acting in a transition system until it stops.

A rollout is the bare agent-environment loop: state, agent, budgets. It knows
nothing about closure, proofs, or SZS -- every proof-specific semantic lives in
the judge that reads its result. By the time a rollout starts, ``P(M)`` exists
and the state is a point in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time

from connections.agent import Agent, AgentStatus
from connections.calculus.actions import Action
from connections.calculus.dynamics import Dynamics
from connections.calculus.state import State
from connections.trace_logging import trace, trace_logger


class Stop(Enum):
    """Why the loop ended: the rollout's own observation.

    ``AGENT_DONE`` is the only stop that consults the agent, and the only one
    for which ``Rollout.status`` is set.
    """

    AGENT_DONE = "agent_done"
    STEP_BUDGET = "step_budget"
    TIME_BUDGET = "time_budget"


@dataclass(frozen=True, slots=True)
class Rollout:
    """What a rollout did, and why it stopped.

    Transitions are deterministic, so when the actions are recorded they and
    the starting state reconstruct every intermediate state; proof replay reads
    exactly this. ``steps`` is counted either way -- with ``record=False``
    there is no action list to derive it from, and the equality of the two is
    a tested invariant rather than a construction.
    """

    state: State
    stop: Stop
    status: AgentStatus | None
    actions: tuple[Action, ...] | None
    steps: int

    def __post_init__(self) -> None:
        if self.actions is not None and len(self.actions) != self.steps:
            raise ValueError("recorded actions disagree with the step count")


def rollout(
    state: State,
    agent: Agent,
    *,
    step_limit: int | None = None,
    deadline: float | None = None,
    record: bool = True,
) -> Rollout:
    """Act in ``P(M)`` from ``state`` until the agent or a budget stops it.

    The state is mutated in place, so several rollouts from one state need a
    copy each. The agent is called at every state it reaches, including a
    final one: closure is the agent's to observe and report, and the judge's
    to verify. ``deadline`` is a ``time.monotonic()`` value checked between
    steps at the same point as ``step_limit``, because the two fail the same
    way -- a step that never returns is a supervisor's problem, not a budget's.
    """

    actions: list[Action] | None = [] if record else None
    steps = 0

    while True:
        if step_limit is not None and steps >= step_limit:
            return Rollout(
                state=state,
                stop=Stop.STEP_BUDGET,
                status=None,
                actions=None if actions is None else tuple(actions),
                steps=steps,
            )
        if deadline is not None and time.monotonic() >= deadline:
            return Rollout(
                state=state,
                stop=Stop.TIME_BUDGET,
                status=None,
                actions=None if actions is None else tuple(actions),
                steps=steps,
            )

        action = agent(state)
        if action is None:
            return Rollout(
                state=state,
                stop=Stop.AGENT_DONE,
                status=agent.status(),
                actions=None if actions is None else tuple(actions),
                steps=steps,
            )

        if actions is not None:
            actions.append(action)
        steps += 1
        Dynamics.transition(state, action)
        trace(trace_logger, action.trace_event())


__all__ = [
    "Rollout",
    "Stop",
    "rollout",
]
