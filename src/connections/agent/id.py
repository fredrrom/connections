"""Iterative deepening over the DFS agent.

The depth ladder, comp switching, and the path-limit condition that decides
whether a fixed point may be claimed. The flag is semantic and set at
detection time: a candidate blocked at the depth gate whose connection
unifies means deeper iterations could differ, so exhaustion without one is a
fixed point. The bookkeeping that emits leanCoP's pathlim_hit events at
leanCoP's positions is trace choreography and lives with pycop's traced
agents in pycop.

The comp switch mutates the options: leanCoP's comp(N) restarts in
complete mode, so cut and scut are turned off on the agent itself, which is
also why _exhaustion_status can rely on them afterwards.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TypeGuard

from connections.agent.base import AgentOptions, AgentStatus
from connections.agent.search import Chooser, OnlineDFSAgent, start_clause_ids
from connections.calculus.actions import Action, ApplyAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import Extension
from connections.calculus.state import State


class OnlineIDAgent(OnlineDFSAgent):
    def __init__(
        self, choose: Chooser, options: AgentOptions | None = None
    ) -> None:
        super().__init__(choose, options)
        self.depth_limit = self.options.initial_depth - 1
        self._path_limit_hit = False

    def _actions_for_goal(self, state: State, goal_id: int) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        if goal.closed:
            return ()
        if Dynamics.regularity_violation(state, goal) is not None:
            return ()
        if goal.goal_id == state.tableau.root_goal_id:
            return tuple(
                ApplyAction(goal_id, rule)
                for rule in Dynamics.start_rules_for(
                    state, start_clause_ids(state.matrix, self.options.start)
                )
            )
        if goal.clause_idx is None or goal.literal_index is None:
            return self._gated_apply_actions(state, goal_id)

        kept: list[Action] = [
            ApplyAction(goal_id, rule)
            for rule in Dynamics.factorization_rules_for(
                state, goal_id, mode=self.options.factorization
            )
        ]
        kept.extend(
            ApplyAction(goal_id, rule)
            for rule in Dynamics.reduction_rules_for(state, goal_id)
        )
        for clause_idx, lit_idx in state.matrix.complements(
            goal.clause_idx, goal.literal_index
        ):
            instance_id = state.fresh_instance_id()
            clause = state.matrix.clauses[clause_idx]
            if goal.depth + 1 >= self.depth_limit and not clause.is_ground:
                if Dynamics.extension_terms_unify_for_position(
                    state, goal_id, clause_idx, lit_idx, instance_id=instance_id
                ):
                    self._path_limit_hit = True
                continue
            action = Dynamics.extension_action_for_position(
                state, goal_id, clause_idx, lit_idx, instance_id=instance_id
            )
            if action is not None:
                kept.append(action)
        return tuple(kept)

    def _gated_apply_actions(self, state: State, goal_id: int) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        actions = super()._actions_for_goal(state, goal_id)
        kept = []
        for action in actions:
            if _is_extension_action(action):
                clause_idx = getattr(action.rule, "clause_idx", None)
                clause = None if clause_idx is None else state.matrix.clauses[clause_idx]
                if (
                    clause is not None
                    and goal.depth + 1 >= self.depth_limit
                    and not clause.is_ground
                ):
                    self._path_limit_hit = True
                    continue
            kept.append(action)
        return tuple(kept)

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                return super()._available_actions(state)
            if not self._stack:
                self.depth_limit += 1
                self._path_limit_hit = False
            actions = super()._available_actions(state)
            if actions:
                return actions
            if not self._should_continue_after_empty_stack():
                return ()
            self._stack.clear()

    def _should_continue_after_empty_stack(self) -> bool:
        if self.options.comp is not None:
            if self.depth_limit >= self.options.comp:
                # leanCoP's comp(N): restart in complete mode. The options
                # are mutated so _exhaustion_status sees the switch.
                self.options = replace(
                    self.options, comp=None, cut=False, scut=False
                )
                self.depth_limit = 0
            return True
        return self._path_limit_hit

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


def _is_extension_action(action: Action) -> TypeGuard[ApplyAction[Extension]]:
    return isinstance(action, ApplyAction) and isinstance(action.rule, Extension)


__all__ = ["OnlineIDAgent"]
