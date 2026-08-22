from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Literal, TypeAlias

from connections.calculus.actions import Action
from connections.calculus.state import State

AgentDecision: TypeAlias = Action | None
StartMode: TypeAlias = Literal["positive", "conjecture"]
BacktrackGranularity: TypeAlias = Literal["step", "maximal"]


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


class AgentStatus(Enum):
    """The agent's word about its own search, in agent vocabulary.

    Values speak about the search, never about the problem. Each member carries
    the one claim the prover reads: whether the agent asserts systematic
    coverage of a complete fragment of the action space. The judge consults
    only ``claims_exhausted``, so a new agent adds a member and its claim
    without the judge learning any new vocabulary.

    ``GAVE_UP`` is the default when an agent returns no action and makes no
    claim. An unsound non-theorem verdict therefore requires an agent to
    overclaim affirmatively, not merely to exist.
    """

    SEARCHING = ("searching", False)
    CLOSED = ("closed", False)
    DFS_EXHAUSTED = ("dfs_exhausted", True)
    ID_FIXED_POINT = ("id_fixed_point", True)
    GAVE_UP = ("gave_up", False)

    def __init__(self, label: str, claims_exhausted: bool) -> None:
        self.label = label
        self.claims_exhausted = claims_exhausted


class Agent(ABC):
    """An agent acting in the transition system: percept in, action out.

    The agent returns actions only. Whether a budget has run out and what any
    of it means for the problem are the prover's to decide, not the agent's.
    The agent is called at every state it reaches, including a final one; it
    observes closure through the percept, settles whatever its memory holds,
    and returns ``None``, after which the rollout ends.

    Everything an agent remembers -- a stack of untried alternatives, a depth
    bound, a search tree, a learned scorer -- is its own state, invisible to
    the transition system.
    """

    @abstractmethod
    def __call__(self, state: State) -> Action | None:
        raise NotImplementedError

    def status(self) -> AgentStatus:
        """Why the last call returned no action, in the agent's vocabulary.

        ``None`` from ``__call__`` is not self-explaining: an exhausted search
        space says something about the problem, an agent with nothing to offer
        says nothing at all. Only the agent knows which, so the rollout asks.
        The default makes no claim.
        """
        return AgentStatus.GAVE_UP


__all__ = [
    "Agent",
    "AgentDecision",
    "AgentStatus",
    "BacktrackGranularity",
    "StartMode",
    "start_clause_ids",
]
