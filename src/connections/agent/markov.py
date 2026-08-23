"""The memoryless agent: a chooser over the currently admissible actions."""

from __future__ import annotations

from connections.agent.base import Agent, AgentOptions, AgentStatus
from connections.agent.base import Chooser
from connections.environment.actions import Action
from connections.environment.dynamics import Dynamics
from connections.environment.state import State


class MarkovAgent(Agent):
    """Chooses among A(s) with no memory at all.

    Every call sees the state fresh: no stack, no bounds, no record of what
    was tried. Useful as the simplest learned-agent shell and as the floor
    other agents are measured against.
    """

    def __init__(self, choose: Chooser, options: AgentOptions | None = None) -> None:
        super().__init__(options)
        self.choose = choose

    def __call__(self, state: State) -> Action | None:
        if state.tableau.root.closed:
            self.status = AgentStatus.CLOSED
            return None
        for goal in state.fringe:
            actions = Dynamics.apply_actions(
                state,
                goal,
                factorization=self.options.factorization,
                start=self.options.start,
            ).ordered()
            if actions:
                self.status = AgentStatus.SEARCHING
                return self.choose(state, actions)
        self.status = AgentStatus.GAVE_UP
        return None


__all__ = ["MarkovAgent"]
