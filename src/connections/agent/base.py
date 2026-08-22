from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypeAlias

from connections.calculus.actions import Action
from connections.calculus.outcome import ProverOutcome
from connections.calculus.state import State


AgentDecision: TypeAlias = Action | None
StartMode: TypeAlias = Literal["positive", "conjecture"]


def start_clause_ids(matrix, mode: StartMode) -> tuple[int, ...]:
    """The clauses this agent asks to start from.

    Selection is the agent's, like factorization: the matrix's role indexes are
    facts, which subset to query is discipline. "conjecture" falls back to the
    positive clauses when the matrix has no conjecture-role clauses, matching
    leanCoP.
    """
    if mode == "conjecture":
        return matrix.conjecture_clauses or matrix.positive_clauses
    return matrix.positive_clauses
BacktrackGranularity: TypeAlias = Literal["step", "maximal"]


class Agent(ABC):
    """An agent acting in the transition system.

    This is the agent-program interface: the policy perceives the current state
    and returns an action, or ``None`` when it has none to offer. It returns
    actions only. Whether a state is terminal, whether a budget has run out, and
    what any of it means are the environment's to decide, not the agent's.

    A rollout stops as soon as it reaches an accepting state, so a policy is
    not called there and should not expect a turn in which to tidy up. Anything
    it wants to survive a proof has to be recorded as it goes.

    Everything a policy remembers -- a stack of untried alternatives, a depth
    bound, a search tree, a learned scorer -- is its own state, invisible to the
    transition system.
    """

    @abstractmethod
    def __call__(self, state: State) -> Action | None:
        raise NotImplementedError

    def stop_reason(self) -> ProverOutcome | None:
        """Why the last call returned no action, if the policy can say.

        Returning ``None`` from ``__call__`` is not self-explaining: a search
        that has exhausted its space says something about the problem, while a
        policy that merely has nothing to offer says nothing at all. Only the
        policy knows which, so the rollout asks rather than guesses.

        The default is ``None``, meaning no claim.
        """
        return None


__all__ = [
    "BacktrackGranularity",
    "AgentDecision",
    "Agent",
]
