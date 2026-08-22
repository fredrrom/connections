"""The memoryless agent: a chooser over the currently admissible actions."""

from __future__ import annotations

from connections.agent.base import Agent, AgentOptions
from connections.agent.search import Chooser
from connections.calculus.actions import Action
from connections.calculus.dynamics import Dynamics
from connections.calculus.state import State
from connections.agent.memory.dfs import start_clause_ids


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
        for goal in state.fringe:
            actions = Dynamics.apply_actions(
                state,
                goal,
                factorization=self.options.factorization,
                start_ids=start_clause_ids(state.matrix, self.options.start),
            ).ordered()
            if actions:
                return self.choose(state, actions)
        return None


__all__ = ["MarkovAgent"]
