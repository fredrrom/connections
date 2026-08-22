"""The model-based agent: memory exposes, a chooser selects.

R&N's model-based agent, specialised to search. The internal state is the
search memory mu; it restricts the actions the environment admits to the ones
the discipline exposes, A(s, mu), and its update is U_pi. The chooser picks
among what is exposed, and nothing else: a learned scorer and leanCoP's
first-choice differ only here.

This factoring is a convenience for reactive agents, not a law. A planner that
runs transitions of its own between percept and action fits neither slot and
implements ``Agent`` directly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from connections.agent.base import Agent, AgentStatus
from connections.calculus.actions import Action
from connections.calculus.state import State

Chooser = Callable[[State, Sequence[Action]], Action]


@runtime_checkable
class Memory(Protocol):
    """Search memory: what A(s, mu) exposes, and how mu updates.

    ``exposed`` also settles the memory's status: when it returns nothing, the
    memory has already decided whether that is closure, an exhaustion it can
    claim, or giving up. ``status`` reports that word.
    """

    def exposed(self, state: State) -> Sequence[Action]: ...

    def update(self, state: State, action: Action) -> None: ...

    def status(self) -> AgentStatus: ...


def first(state: State, actions: Sequence[Action]) -> Action:
    """leanCoP's chooser: the first exposed action, in discipline order."""
    _ = state
    return actions[0]


class ModelBasedAgent(Agent):
    """An agent composed of a search memory and a chooser."""

    def __init__(self, memory: Memory, choose: Chooser = first) -> None:
        self.memory = memory
        self.choose = choose

    def __call__(self, state: State) -> Action | None:
        exposed = self.memory.exposed(state)
        if not exposed:
            return None
        action = self.choose(state, exposed)
        self.memory.update(state, action)
        return action

    def status(self) -> AgentStatus:
        return self.memory.status()


__all__ = [
    "Chooser",
    "Memory",
    "ModelBasedAgent",
    "first",
]
