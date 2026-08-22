from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from typing import Literal

from connections.env.actions import Action
from connections.env.rules import FactorizationMode
from connections.env.state import State

Chooser = Callable[[State, Sequence[Action]], Action]


class AgentStatus(Enum):
    """What the agent reports about its own search.

    The mapping from statuses to outcomes and SZS verdicts lives in ``run``,
    next to the judge.
    """

    SEARCHING = "searching"
    CLOSED = "closed"
    DFS_EXHAUSTED = "dfs_exhausted"
    ID_FIXED_POINT = "id_fixed_point"
    GAVE_UP = "gave_up"


@dataclass(frozen=True)
class AgentOptions:
    """Options an agent is constructed with.

    A flat record: agents read the fields they care about and ignore the
    rest. A markov agent reads only ``start`` and ``factorization``; the
    search memories read all of them.
    """

    cut: bool = False
    scut: bool = False
    comp: int | None = None
    backtrack: Literal["step", "maximal"] = "step"
    factorization: FactorizationMode = "unify"
    start: Literal["positive", "conjecture"] = "positive"
    initial_depth: int = 1


class Agent(ABC):
    """An agent acting in the transition system: percept in, action out.

    The agent returns actions only; returning ``None`` ends the rollout.
    ``status`` is a plain attribute reporting the state of the agent's own
    search, updated as the agent acts.
    """

    def __init__(self, options: AgentOptions | None = None) -> None:
        self.options = options if options is not None else AgentOptions()
        self.status = AgentStatus.SEARCHING

    @abstractmethod
    def __call__(self, state: State) -> Action | None:
        raise NotImplementedError


__all__ = [
    "Agent",
    "AgentOptions",
    "AgentStatus",
    "Chooser",
]
