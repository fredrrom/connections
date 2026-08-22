"""Iterative deepening over the DFS memory.

The depth ladder, comp switching, and the path-limit discipline that decides
whether a fixed point may be claimed. The path-limit flag is semantic and set
at detection time: a candidate blocked at the depth gate whose connection
unifies means deeper iterations could differ, so exhaustion without one is a
fixed point. The deferred hit bookkeeping that emits leanCoP's pathlim_hit
events at leanCoP's positions is trace choreography and lives with pycop's
traced memories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

from connections.agent.base import AgentStatus, StartMode, start_clause_ids
from connections.agent.dfs import DFSMemory
from connections.agent.memory import ModelBasedAgent, first
from connections.calculus.actions import Action, ApplyAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import Extension, FactorizationMode
from connections.calculus.state import State


@dataclass(frozen=True, slots=True)
class IterativeDeepeningOptions:
    initial_depth: int = 1
    comp: int | None = None


class IDMemory(DFSMemory):
    def __init__(
        self,
        *,
        cut: bool = False,
        scut: bool = False,
        comp: int | None = None,
        backtrack: str = "step",
        factorization: FactorizationMode = "unify",
        start: StartMode = "positive",
        initial_depth: int = 1,
    ) -> None:
        super().__init__(
            cut=cut,
            scut=scut,
            backtrack=backtrack,
            factorization=factorization,
            start=start,
        )
        if initial_depth < 1:
            raise ValueError("initial_depth must be at least 1")
        self.comp = comp
        self.depth_limit = initial_depth - 1
        self._path_limit_hit = False

    def _actions_for_goal(self, state: State, goal_id: int) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        if goal.closed:
            return ()
        if Dynamics.regularity_violation(state, goal) is not None:
            return ()
        if goal.goal_id == self._root_goal_id(state):
            return tuple(
                ApplyAction(goal_id, rule)
                for rule in Dynamics.start_rules_for(
                    state, start_clause_ids(state.matrix, self.start)
                )
            )
        if goal.clause_idx is None or goal.literal_index is None:
            return self._gated_apply_actions(state, goal_id)

        kept: list[Action] = [
            ApplyAction(goal_id, rule)
            for rule in Dynamics.factorization_rules_for(
                state, goal_id, mode=self.factorization
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
                clause = self._extension_clause(state, action)
                if (
                    clause is not None
                    and goal.depth + 1 >= self.depth_limit
                    and not clause.is_ground
                ):
                    self._path_limit_hit = True
                    continue
            kept.append(action)
        return tuple(kept)

    @staticmethod
    def _extension_clause(state: State, action: ApplyAction[Extension]):
        clause_idx = getattr(action.rule, "clause_idx", None)
        if clause_idx is None:
            return None
        return state.matrix.clauses[clause_idx]

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                return super()._available_actions(state)
            if not self._stack:
                self._start_next_depth()
            actions = super()._available_actions(state)
            if actions:
                return actions
            if not self._should_continue_after_empty_stack():
                return ()
            self._reset_search(state)

    def _start_next_depth(self) -> None:
        self.depth_limit += 1
        self._path_limit_hit = False

    def _should_continue_after_empty_stack(self) -> bool:
        if self.comp is not None:
            if self.depth_limit >= self.comp:
                # leanCoP's comp(N): restart in complete mode.
                self.comp = None
                self.cut_enabled = False
                self.scut_enabled = False
                self.depth_limit = 0
            return True
        return self._path_limit_hit

    def _reset_search(self, state: State) -> None:
        _ = state
        self._stack.clear()

    def _exhaustion_status(self) -> AgentStatus:
        """A fixed point is claimable only from a complete final iteration.

        By the time the ladder stops, a comp() switch has already turned cut
        and scut off; if they are still on, the space was pruned and the claim
        is forfeit.
        """
        if (
            self.comp is None
            and not self.cut_enabled
            and not self.scut_enabled
            and self.start == "positive"
            and not self._path_limit_hit
        ):
            return AgentStatus.ID_FIXED_POINT
        return AgentStatus.GAVE_UP


def _is_extension_action(action: Action) -> TypeGuard[ApplyAction[Extension]]:
    return isinstance(action, ApplyAction) and isinstance(action.rule, Extension)


def first_action_id_agent(**options) -> ModelBasedAgent:
    """leanCoP's agent: iterative-deepening memory, first-choice chooser."""
    return ModelBasedAgent(IDMemory(**options), first)


__all__ = [
    "IDMemory",
    "IterativeDeepeningOptions",
    "first_action_id_agent",
]
