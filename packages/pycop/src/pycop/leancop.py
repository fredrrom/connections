"""leanCoP as an agent: the iterative-deepening search with a first chooser.

There is no separate leanCoP implementation. ``OnlineIDAgent`` already
searches the way leanCoP does and emits leanCoP's trace events at leanCoP's
positions; what makes it leanCoP is the ``first`` chooser and leanCoP's
option spellings, which is all this module adds.
"""

from __future__ import annotations

from collections.abc import Sequence

from connections.agent.base import AgentOptions
from connections.agent.id import OnlineIDAgent
from connections.environment.actions import Action
from connections.environment.rules import FactorizationMode
from connections.environment.state import State


def first(state: State, actions: Sequence[Action]) -> Action:
    """leanCoP's chooser: the first exposed action, in memory order."""
    _ = state
    return actions[0]


def leancop_agent(
    *,
    cut: bool = False,
    scut: bool = False,
    comp: int | None = None,
    backtrack: str = "step",
    factorization: FactorizationMode = "unify",
    start: str = "positive",
    initial_depth: int = 1,
) -> OnlineIDAgent:
    return OnlineIDAgent(
        first,
        AgentOptions(
            cut=cut,
            scut=scut,
            comp=comp,
            backtrack=backtrack,  # type: ignore[arg-type]
            factorization=factorization,
            start=start,  # type: ignore[arg-type]
            initial_depth=initial_depth,
        ),
    )


__all__ = ["first", "leancop_agent"]
