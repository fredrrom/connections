"""A policy acting in a transition system until it stops.

A rollout is the smallest unit of proof search. It takes no problem, no
schedule and no clausification: by the time one starts, ``P(M)`` exists and the
state is a point in it.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import cast

from connections.calculus.actions import Action, ApplyAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.outcome import ProverOutcome
from connections.calculus.state import State
from connections.policy import Policy
from connections.trace_logging import trace, trace_logger


@dataclass(frozen=True, slots=True)
class Rollout:
    """What a rollout did, and why it stopped.

    Transitions are deterministic, so the action sequence together with the
    starting state reconstructs every intermediate state. Nothing else needs
    storing, and proof replay reads exactly this.
    """

    actions: tuple[Action, ...]
    state: State
    outcome: ProverOutcome | None

    @property
    def steps(self) -> int:
        """Transition steps: applications of ``T``.

        This is the portable effort measure, and the one budgets are set in.
        """
        return len(self.actions)

    @property
    def inference_steps(self) -> int:
        """Inference steps: rule applications recorded in the proof object.

        An append performs one; a prune removes one or more, so this is never
        larger than ``steps``.
        """
        return sum(1 for action in self.actions if isinstance(action, ApplyAction))

    @property
    def proved(self) -> bool:
        return self.outcome is ProverOutcome.PROVED


def _closed(state: State) -> bool:
    return state.tableau.root.closed and state.constraints.satisfiable(
        logic=state.problem.logic,
        domain=state.problem.domain,
    )


def rollout(
    state: State,
    *,
    policy: Policy,
    step_limit: int | None = None,
    deadline: float | None = None,
) -> Rollout:
    """Act in ``P(M)`` from ``state`` until the policy or a budget stops it.

    The state is mutated in place, so several rollouts from one state need a
    copy each. That is not too expensive: the matrix is immutable and shared,
    and only the tableau and constraint store are duplicated.

    ``deadline`` is a ``time.monotonic()`` value, checked between steps at the
    same point as ``step_limit`` because the two fail the same way: a step that
    never returns means the loop that would have noticed either limit is never
    reached. Guaranteeing termination against that needs something that can
    kill the process.

    Both budgets report ``TIME_BUDGET``/``STEP_BUDGET`` rather than ``TIMEOUT``.
    From inside, an allotment ran out, which is ``ResourceOut``; ``Timeout`` is
    a claim about a process and belongs to whatever supervises it.
    """

    actions: list[Action] = []
    outcome: ProverOutcome | None = None

    while True:
        if _closed(state):
            outcome = ProverOutcome.PROVED
            break
        if step_limit is not None and len(actions) >= step_limit:
            outcome = ProverOutcome.STEP_BUDGET
            break
        if deadline is not None and time.monotonic() >= deadline:
            outcome = ProverOutcome.TIME_BUDGET
            break

        decision = cast(Action | ProverOutcome | None, policy(state))
        if isinstance(decision, ProverOutcome):
            outcome = decision
            break
        if decision is None:
            break

        actions.append(decision)
        Dynamics.transition(state, decision)
        trace(trace_logger, decision.trace_event())

        if _closed(state):
            policy.on_tableau_closed(state)
            outcome = ProverOutcome.PROVED
            break

    return Rollout(actions=tuple(actions), state=state, outcome=outcome)


__all__ = [
    "Rollout",
    "rollout",
]
