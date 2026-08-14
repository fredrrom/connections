from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypeAlias

from connections.calculus.actions import Action
from connections.calculus.state import State


PolicyDecision: TypeAlias = Action | None
BacktrackGranularity: TypeAlias = Literal["step", "maximal"]


class Policy(ABC):
    """A choice among the actions the calculus admits at a state.

    The only required operation is calling the policy with the current state.
    Plain policies return an action or ``None``. Policies with memory may also
    return a prover outcome, which is how they say *why* nothing is left --
    something an empty action set cannot distinguish from a budget running out.

    Everything a policy remembers -- a stack of untried alternatives, a depth
    bound, a search tree, a learned scorer -- is its own state, invisible to the
    transition system.
    """

    @abstractmethod
    def __call__(self, state: State) -> object:
        raise NotImplementedError

    def on_tableau_closed(self, state: State) -> None:
        """Notify the policy that the tableau closed after its last action.

        A rollout calls this before it stops, so a policy whose memory holds
        commitments that only become final on success can settle them. The
        default does nothing; policies without such memory need not care.
        """
        _ = state


__all__ = [
    "BacktrackGranularity",
    "PolicyDecision",
    "Policy",
]
