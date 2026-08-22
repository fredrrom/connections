"""Iterative deepening: DFS with a depth gate and a ladder.

The gate is the one real change to the search: extension candidates whose
clause is not ground are withheld once the path is at the depth limit. A
withheld candidate whose connection unifies sets the path-limit flag --
deeper iterations could differ -- and queues a ``pathlim_hit`` trace token
in its place, so the event fires exactly where leanCoP's candidate
iteration would reach it. On modal matrices the candidates are the
term-unifiable positions, not just the admissible actions, since leanCoP's
modal variants count those against the gate too.

The ladder restarts the search one limit deeper whenever an iteration
exhausts with the flag set. leanCoP's comp(N) switches to complete mode at
depth N by mutating the options -- cut and scut off -- which is also why
``_exhaustion_status`` can rely on them afterwards: a fixed point is
claimable only from a complete final iteration.
"""

from __future__ import annotations

from dataclasses import replace

from connections.agent.base import AgentOptions, AgentStatus, Chooser
from connections.agent.dfs import OnlineDFSAgent, TraceToken
from connections.env.actions import Action, ApplyAction
from connections.env.dynamics import Dynamics
from connections.env.rules import Extension
from connections.env.state import State
from connections.trace_logging import trace, trace_logger

_MODAL_LOGICS = frozenset({"D", "T", "S4", "S5"})
_PATH_LIMIT_HIT = TraceToken("pathlim_hit")


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

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                # The final call: settle closed goals and yield nothing.
                # Deepening at a closed root would be spurious work and a
                # spurious pathlim trace.
                return super()._available_actions(state)
            if self._fresh_iteration:
                self._fresh_iteration = False
                previous_depth_limit = self.depth_limit
                self.depth_limit += 1
                self._path_limit_hit = False
                if previous_depth_limit > 0:
                    trace(trace_logger, "pathlim")
            actions = super()._available_actions(state)
            if actions:
                return actions
            if not self._deepen():
                return ()
            self._alternatives.clear()
            self._committed.clear()
            self._scut_goal_id = None
            self._fresh_iteration = True

    def _deepen(self) -> bool:
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

    def _on_new_episode(self) -> None:
        super()._on_new_episode()
        # The comp switch mutates the options; a fresh episode starts from the
        # options the agent was constructed with.
        self.options = self._constructed_options
        self.depth_limit = self.options.initial_depth - 1
        self._path_limit_hit = False
        self._fresh_iteration = True

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

    # -- the depth gate -----------------------------------------------------

    def _actions_for_goal(
        self, state: State, goal_id: int
    ) -> tuple[Action | TraceToken, ...]:
        goal = state.tableau.goals[goal_id]
        if Dynamics.regularity_violation(state, goal) is not None:
            trace(trace_logger, "regularity")
            return ()
        if goal.goal_id == state.tableau.root_goal_id:
            return tuple(
                ApplyAction(goal_id, rule)
                for rule in Dynamics.start_rules_for(state, self.options.start)
            )
        at_limit = goal.depth + 1 >= self.depth_limit
        if goal.clause_idx is None or goal.literal_index is None:
            actions = super()._actions_for_goal(state, goal_id)
            kept = [action for action in actions if not _is_extension(action)]
            extensions = [action for action in actions if _is_extension(action)]
            for action, clause in self._term_candidates(state, goal_id, extensions):
                if at_limit and not clause.is_ground:
                    self._path_limit_hit = True
                    kept.append(_PATH_LIMIT_HIT)
                elif action is not None:
                    kept.append(action)
            return tuple(kept)

        kept = [
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
            if at_limit and not state.matrix.clauses[clause_idx].is_ground:
                if Dynamics.extension_terms_unify_for_position(
                    state, goal_id, clause_idx, lit_idx, instance_id=instance_id
                ):
                    self._path_limit_hit = True
                    kept.append(_PATH_LIMIT_HIT)
                continue
            action = Dynamics.extension_action_for_position(
                state, goal_id, clause_idx, lit_idx, instance_id=instance_id
            )
            if action is not None:
                kept.append(action)
        return tuple(kept)

    def _term_candidates(self, state: State, goal_id: int, extensions: list):
        """Extension candidates for goals without a matrix position.

        Classically these are just the admissible extension actions; on
        modal matrices leanCoP counts every term-unifiable position against
        the gate, so the scan pairs each position with its action when one
        exists and its clause regardless.
        """
        if state.matrix.logic not in _MODAL_LOGICS:
            return [(action, action.rule.clause) for action in extensions]
        by_key = {
            (action.rule.clause_idx, action.rule.lit_idx): action
            for action in extensions
        }
        candidates = []
        for key in Dynamics.extension_term_candidate_positions_for(state, goal_id):
            action = by_key.get(key)
            clause = (
                action.rule.clause
                if action is not None
                else state.matrix.clauses[key[0]]
            )
            candidates.append((action, clause))
        return candidates


def _is_extension(action: Action | TraceToken) -> bool:
    return isinstance(action, ApplyAction) and isinstance(action.rule, Extension)


__all__ = ["OnlineIDAgent"]
