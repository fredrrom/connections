"""The online search agent: memory exposes, a chooser selects.

The memory is the agent's search state. It restricts the actions the
environment admits to the ones it exposes, A(s, mu), and its update is U_pi.
The chooser picks among what is exposed, and nothing else: leanCoP's
first-choice and a learned scorer differ only here.

A planner that runs transitions of its own between percept and action fits
neither slot and implements ``Agent`` directly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from connections.agent.base import Agent, AgentOptions
from connections.calculus.actions import Action
from connections.calculus.state import State

Chooser = Callable[[State, Sequence[Action]], Action]


@runtime_checkable
class Memory(Protocol):
    """Search state: what A(s, mu) exposes, and how mu updates.

    Both methods receive the agent: the memory reads its configuration from
    ``agent.options`` and maintains ``agent.status`` as it learns why there
    is or is not anything left to expose.
    """

    def exposed(self, agent: Agent, state: State) -> Sequence[Action]: ...

    def update(self, agent: Agent, state: State, action: Action) -> None: ...


class OnlineSearchAgent(Agent):
    """An agent composed of a search memory and a chooser."""

    def __init__(
        self,
        memory: Memory,
        choose: Chooser,
        options: AgentOptions | None = None,
    ) -> None:
        super().__init__(options)
        self.memory = memory
        self.choose = choose

    def __call__(self, state: State) -> Action | None:
        exposed = self.memory.exposed(self, state)
        if not exposed:
            return None
        action = self.choose(state, exposed)
        self.memory.update(self, state, action)
        return action


__all__ = [
    "Chooser",
    "Memory",
    "OnlineSearchAgent",
]
