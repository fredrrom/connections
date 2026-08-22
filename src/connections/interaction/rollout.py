"""An agent acting in a transition system until it stops.

A rollout is the bare agent-environment loop: state, agent, budgets. It knows
nothing about closure, proofs, or SZS -- every proof-specific semantic lives in
the judge that reads its result. The agent-environment split is an
architecture, not a trust boundary: everything on both sides is one program,
and soundness rests on the environment admitting only valid edits. By the time a rollout starts, ``P(M)`` exists
and the state is a point in it.
"""

from __future__ import annotations

import time

from connections.agent import Agent
from connections.env.actions import Action
from connections.env.dynamics import Dynamics
from connections.env.state import State
from connections.interaction.records import Rollout
from connections.interaction.truncation import Truncation
from connections.trace_logging import trace, trace_logger



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
    final one: closure is the agent's to observe and report, and the judge
    believes it. ``deadline`` is a ``time.monotonic()`` value checked between
    steps at the same point as ``step_limit``, because the two fail the same
    way -- a step that never returns is a supervisor's problem, not a budget's.
    """

    actions: list[Action] | None = [] if record else None
    steps = 0

    while True:
        if step_limit is not None and steps >= step_limit:
            return Rollout(
                state=state,
                status=None,
                truncation=Truncation.STEPS,
                actions=None if actions is None else tuple(actions),
                steps=steps,
            )
        if deadline is not None and time.monotonic() >= deadline:
            return Rollout(
                state=state,
                status=None,
                truncation=Truncation.TIME,
                actions=None if actions is None else tuple(actions),
                steps=steps,
            )

        action = agent(state)
        if action is None:
            return Rollout(
                state=state,
                status=agent.status,
                truncation=None,
                actions=None if actions is None else tuple(actions),
                steps=steps,
            )

        if actions is not None:
            actions.append(action)
        steps += 1
        Dynamics.transition(state, action)
        trace(trace_logger, action.trace_event())


__all__ = [
    "rollout",
]
