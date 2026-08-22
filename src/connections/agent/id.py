"""Iterative deepening: DFS querying actions under a depth limit.

The depth gate itself lives in ``Dynamics.apply_actions`` as the
``depth_limit`` query option, like ``start`` and ``factorization``. The
agent turns each reported withheld-but-unifiable candidate into the
path-limit flag -- deeper iterations could differ, so exhaustion without
one is a fixed point -- and a ``pathlim_hit`` trace token at the
candidate's position. leanCoP's comp(N) switches to complete mode at depth
N by mutating the options, cut and scut off, which is why
``_exhaustion_status`` can rely on them afterwards.
"""

from __future__ import annotations

from dataclasses import replace

from connections.agent.base import AgentOptions, AgentStatus, Chooser
from connections.agent.dfs import OnlineDFSAgent, TraceToken
from connections.env.actions import Action
from connections.env.dynamics import Dynamics
from connections.env.state import State
from connections.trace_logging import trace, trace_logger

_PATH_LIMIT_HIT = TraceToken("pathlim_hit")


class OnlineIDAgent(OnlineDFSAgent):
    def __init__(
        self, choose: Chooser, options: AgentOptions | None = None
    ) -> None:
        super().__init__(choose, options)
        if self.options.initial_depth < 1:
            raise ValueError("initial_depth must be at least 1")
        self._constructed_options = self.options
        self.depth_limit = self.options.initial_depth
        self._path_limit_hit = False

    def _actions_for_goal(
        self, state: State, goal_id: int
    ) -> tuple[Action | TraceToken, ...]:
        actions = Dynamics.apply_actions(
            state,
            state.tableau.goals[goal_id],
            factorization=self.options.factorization,
            start=self.options.start,
            depth_limit=self.depth_limit,
        )
        if not actions.path_limit_hits:
            return actions.ordered()
        self._path_limit_hit = True
        stream: list[Action | TraceToken] = list(
            actions.start + actions.factorization + actions.reduction
        )
        hits = list(actions.path_limit_hits)
        for index, action in enumerate(actions.extension):
            while hits and hits[0] <= index:
                hits.pop(0)
                stream.append(_PATH_LIMIT_HIT)
            stream.append(action)
        stream.extend(_PATH_LIMIT_HIT for _ in hits)
        return tuple(stream)

    def _next_iteration(self) -> bool:
        options = self.options
        if options.comp is not None:
            if self.depth_limit >= options.comp:
                # leanCoP's comp(N): restart in complete mode. The options
                # are mutated so _exhaustion_status sees the switch.
                self.options = replace(options, comp=None, cut=False, scut=False)
                self.depth_limit = 0
        elif not self._path_limit_hit:
            return False
        if self.depth_limit > 0:
            trace(trace_logger, "pathlim")
        self.depth_limit += 1
        self._path_limit_hit = False
        return True

    def _on_new_episode(self) -> None:
        super()._on_new_episode()
        # The comp switch mutates the options; a fresh episode starts from the
        # options the agent was constructed with.
        self.options = self._constructed_options
        self.depth_limit = self.options.initial_depth
        self._path_limit_hit = False
        if self.depth_limit > 1:
            trace(trace_logger, "pathlim")

    def _exhaustion_status(self) -> AgentStatus:
        """A fixed point is claimable only from a complete final iteration."""
        options = self.options
        if (
            options.comp is None
            and not options.cut
            and not options.scut
            and options.start == "positive"
            and not self._path_limit_hit
        ):
            return AgentStatus.ID_FIXED_POINT
        return AgentStatus.GAVE_UP


__all__ = ["OnlineIDAgent"]
