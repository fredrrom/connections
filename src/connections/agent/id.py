"""Iterative deepening over the DFS agent.

The depth ladder, comp switching, and the path-limit condition that decides
whether a fixed point may be claimed. The flag is semantic and set at
detection time: a candidate blocked at the depth gate whose connection
unifies means deeper iterations could differ, so exhaustion without one is
a fixed point. On modal matrices the candidates are the term-unifiable
positions, not just the admissible actions, since leanCoP's modal variants
count a blocked candidate as a hit whenever its terms unify.

The agent also emits leanCoP's trace events at leanCoP's positions:
``pathlim`` when the ladder deepens, ``regularity`` when a goal is pruned,
and ``pathlim_hit`` per blocked candidate, deferred to where leanCoP's
candidate iteration would reach it -- just before the next kept extension
is taken, or when the goal is abandoned.

The comp switch mutates the options: leanCoP's comp(N) restarts in
complete mode, so cut and scut are turned off on the agent itself, which is
also why _exhaustion_status can rely on them afterwards.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TypeGuard

from connections.agent.base import AgentOptions, AgentStatus, Chooser
from connections.agent.dfs import OnlineDFSAgent
from connections.env.actions import Action, ApplyAction
from connections.env.dynamics import Dynamics
from connections.env.rules import Extension
from connections.env.state import State
from connections.syntax.matrix import Clause
from connections.trace_logging import trace, trace_logger

_MODAL_LOGICS = frozenset({"D", "T", "S4", "S5"})


class OnlineIDAgent(OnlineDFSAgent):
    def __init__(
        self, choose: Chooser, options: AgentOptions | None = None
    ) -> None:
        super().__init__(choose, options)
        if self.options.initial_depth < 1:
            raise ValueError("initial_depth must be at least 1")
        self._constructed_options = self.options
        self.depth_limit = self.options.initial_depth - 1
        self._path_limit_hit = False
        self._fresh_iteration = True
        self._hits_before_action: dict[int, dict[int, int]] = {}
        self._terminal_hits: dict[int, int] = {}

    # -- the depth ladder ---------------------------------------------------

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                # The final call: settle closed goals and yield nothing.
                # Bumping the depth ladder at a closed root would be spurious
                # work and a spurious pathlim trace.
                return super()._available_actions(state)
            if self._fresh_iteration:
                self._fresh_iteration = False
                self._start_next_depth()
            actions = super()._available_actions(state)
            if actions:
                return actions
            if not self._should_continue_after_empty_stack():
                return ()
            self._reset_iteration()

    def _start_next_depth(self) -> None:
        previous_depth_limit = self.depth_limit
        self.depth_limit += 1
        self._path_limit_hit = False
        if previous_depth_limit > 0:
            trace(trace_logger, "pathlim")

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

    def _reset_iteration(self) -> None:
        self._alternatives.clear()
        self._committed.clear()
        self._scut_goal_id = None
        self._hits_before_action.clear()
        self._terminal_hits.clear()
        self._fresh_iteration = True

    def _on_new_episode(self) -> None:
        super()._on_new_episode()
        # The comp switch mutates the options; a fresh episode starts from the
        # options the agent was constructed with.
        self.options = self._constructed_options
        self.depth_limit = self.options.initial_depth - 1
        self._path_limit_hit = False
        self._fresh_iteration = True
        self._hits_before_action.clear()
        self._terminal_hits.clear()

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

    # -- depth-gated action generation --------------------------------------

    def _actions_for_goal(self, state: State, goal_id: int) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        if Dynamics.regularity_violation(state, goal) is not None:
            trace(trace_logger, "regularity")
            return ()
        if goal.goal_id == state.tableau.root_goal_id:
            return tuple(
                ApplyAction(goal_id, rule)
                for rule in Dynamics.start_rules_for(state, self.options.start)
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
        hits_before_action: dict[int, int] = {}
        pending_hits = 0
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
                    pending_hits += 1
                continue
            action = Dynamics.extension_action_for_position(
                state, goal_id, clause_idx, lit_idx, instance_id=instance_id
            )
            if action is None:
                continue
            if pending_hits:
                hits_before_action[id(action)] = pending_hits
                pending_hits = 0
            kept.append(action)
        self._record_hit_positions(goal_id, hits_before_action, pending_hits)
        return tuple(kept)

    def _gated_apply_actions(self, state: State, goal_id: int) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        actions = super()._actions_for_goal(state, goal_id)
        kept = [action for action in actions if not _is_extension_action(action)]
        extension_actions = [
            action for action in actions if _is_extension_action(action)
        ]
        hits_before_action: dict[int, int] = {}
        pending_hits = 0
        for action, clause in self._extension_candidates(
            state, goal_id, extension_actions
        ):
            if goal.depth + 1 >= self.depth_limit and not clause.is_ground:
                self._path_limit_hit = True
                pending_hits += 1
                continue
            if action is None:
                continue
            if pending_hits:
                hits_before_action[id(action)] = pending_hits
                pending_hits = 0
            kept.append(action)
        self._record_hit_positions(goal_id, hits_before_action, pending_hits)
        return tuple(kept)

    def _extension_candidates(
        self,
        state: State,
        goal_id: int,
        extension_actions: list[ApplyAction[Extension]],
    ) -> tuple[tuple[ApplyAction[Extension] | None, Clause], ...]:
        """Candidates in leanCoP's order; on modal matrices, by term positions.

        A modal candidate whose terms unify counts against the depth gate even
        when it is not an admissible action, so the scan pairs each candidate
        position with its action when one exists and its clause regardless.
        """
        if state.matrix.logic not in _MODAL_LOGICS:
            return tuple((action, action.rule.clause) for action in extension_actions)
        extension_actions_by_key = {
            (action.rule.clause_idx, action.rule.lit_idx): action
            for action in extension_actions
        }
        candidates: list[tuple[ApplyAction[Extension] | None, Clause]] = []
        for key in Dynamics.extension_term_candidate_positions_for(state, goal_id):
            action = extension_actions_by_key.get(key)
            clause = (
                action.rule.clause
                if action is not None
                else state.matrix.clauses[key[0]]
            )
            candidates.append((action, clause))
        return tuple(candidates)

    # -- pathlim_hit choreography -------------------------------------------

    def _record_hit_positions(
        self, goal_id: int, hits_before_action: dict[int, int], terminal_hits: int
    ) -> None:
        if hits_before_action:
            self._hits_before_action[goal_id] = hits_before_action
        if terminal_hits:
            self._terminal_hits[goal_id] = terminal_hits

    def _before_action(self, action: ApplyAction) -> None:
        hits = self._hits_before_action.get(action.goal_id)
        if hits is not None:
            self._emit_path_limit_hits(hits.pop(id(action), 0))

    def _abandon(self, goal_id: int) -> None:
        self._emit_path_limit_hits(self._terminal_hits.get(goal_id, 0))
        super()._abandon(goal_id)

    def _forget(self, goal_id: int) -> None:
        super()._forget(goal_id)
        self._hits_before_action.pop(goal_id, None)
        self._terminal_hits.pop(goal_id, None)

    @staticmethod
    def _emit_path_limit_hits(count: int) -> None:
        for _ in range(count):
            trace(trace_logger, "pathlim_hit")


def _is_extension_action(action: Action) -> TypeGuard[ApplyAction[Extension]]:
    return isinstance(action, ApplyAction) and isinstance(action.rule, Extension)


__all__ = ["OnlineIDAgent"]
