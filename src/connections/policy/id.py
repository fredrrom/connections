from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

from connections.core.matrix import Clause
from connections.core.status import ProverOutcome
from connections.policy.base import BacktrackGranularity
from connections.policy.dfs import DFSPolicy, Frame
from connections.prover.actions import Action, ApplyAction, UndoAction
from connections.prover.dynamics import Dynamics
from connections.prover.rules import Extension, FactorizationMode
from connections.prover.state import State
from connections.trace_logging import trace, trace_logger

_MODAL_LOGICS = frozenset({"D", "T", "S4", "S5"})
ExtensionKey = tuple[int | None, int]


@dataclass(frozen=True, slots=True)
class IterativeDeepeningOptions:
    comp: int | None = None
    initial_depth: int = 1


class IterativeDeepeningPolicy(DFSPolicy):
    def __init__(
        self,
        *,
        cut: bool = False,
        scut: bool = False,
        comp: int | None = None,
        backtrack: BacktrackGranularity = "step",
        factorization: FactorizationMode = "unify",
        initial_depth: int = 1,
    ) -> None:
        super().__init__(
            cut=cut,
            scut=scut,
            backtrack=backtrack,
            factorization=factorization,
        )
        if initial_depth < 1:
            raise ValueError("initial_depth must be at least 1")
        self.comp = comp
        self.depth_limit = initial_depth - 1
        self._path_limit_hit = False
        self._pending_path_limit_plan: tuple[int, dict[int, int], int] | None = None
        self._path_limit_hits_before_action: dict[int, dict[int, int]] = {}
        self._terminal_path_limit_hits: dict[int, int] = {}

    def _actions_for_goal(
        self,
        state: State,
        goal_id: int,
    ) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        if goal.closed:
            self._pending_path_limit_plan = (goal_id, {}, 0)
            return ()
        if Dynamics.regularity_violation(state, goal) is not None:
            trace(trace_logger, "regularity")
            self._pending_path_limit_plan = (goal_id, {}, 0)
            return ()
        root_goal_id = getattr(state.tableau, "root_goal_id", state.tableau.root.goal_id)
        if goal.goal_id == root_goal_id:
            self._pending_path_limit_plan = (goal_id, {}, 0)
            return tuple(
                ApplyAction(goal_id, rule)
                for rule in Dynamics.start_rules_for(state, goal_id)
            )
        if (
            getattr(goal, "clause_idx", None) is None
            or getattr(goal, "literal_index", None) is None
        ):
            return self._actions_from_apply_actions(state, goal_id)

        kept: list[Action] = [
            ApplyAction(goal_id, rule)
            for rule in Dynamics.factorization_rules_for(
                state,
                goal_id,
                mode=self.factorization,
            )
        ]
        kept.extend(
            ApplyAction(goal_id, rule)
            for rule in Dynamics.reduction_rules_for(state, goal_id)
        )
        hits_before_action: dict[int, int] = {}
        pending_hits = 0
        if goal.clause_idx is not None and goal.literal_index is not None:
            for clause_idx, lit_idx in state.problem.matrix.complements(
                goal.clause_idx,
                goal.literal_index,
            ):
                instance_id = state.fresh_instance_id()
                clause = state.problem.matrix.clauses[clause_idx]
                if goal.depth + 1 >= self.depth_limit and not clause.is_ground:
                    if Dynamics.extension_terms_unify_for_position(
                        state,
                        goal_id,
                        clause_idx,
                        lit_idx,
                        instance_id=instance_id,
                    ):
                        self._path_limit_hit = True
                        pending_hits += 1
                    continue
                action = Dynamics.extension_action_for_position(
                    state,
                    goal_id,
                    clause_idx,
                    lit_idx,
                    instance_id=instance_id,
                )
                if action is None:
                    continue
                if pending_hits:
                    hits_before_action[id(action)] = pending_hits
                    pending_hits = 0
                kept.append(action)
        self._pending_path_limit_plan = (
            goal_id,
            hits_before_action,
            pending_hits,
        )
        return tuple(kept)

    def _actions_from_apply_actions(
        self,
        state: State,
        goal_id: int,
    ) -> tuple[Action, ...]:
        goal = state.tableau.goals[goal_id]
        actions = super()._actions_for_goal(state, goal_id)
        kept = [action for action in actions if not _is_extension_action(action)]
        extension_actions = [
            action for action in actions if _is_extension_action(action)
        ]
        hits_before_action: dict[int, int] = {}
        pending_hits = 0
        for action, clause in self._extension_candidates(
            state,
            goal_id,
            extension_actions,
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
        self._pending_path_limit_plan = (
            goal_id,
            hits_before_action,
            pending_hits,
        )
        return tuple(kept)

    def _extension_candidates(
        self,
        state: State,
        goal_id: int,
        extension_actions: list[ApplyAction[Extension]],
    ) -> tuple[tuple[ApplyAction[Extension] | None, Clause], ...]:
        if state.problem.logic not in _MODAL_LOGICS:
            return tuple((action, action.rule.clause) for action in extension_actions)

        goal = state.tableau.goals[goal_id]
        if Dynamics.regularity_violation(state, goal) is not None:
            return ()

        extension_actions_by_key = {
            (action.rule.clause_idx, action.rule.lit_idx): action
            for action in extension_actions
        }
        candidates: list[tuple[ApplyAction[Extension] | None, Clause]] = []
        for key in Dynamics.extension_term_candidate_positions_for(state, goal_id):
            action = extension_actions_by_key.get(key)
            candidates.append((action, self._extension_clause(state, key, action)))
        return tuple(candidates)

    @staticmethod
    def _extension_clause(
        state: State,
        key: ExtensionKey,
        action: ApplyAction[Extension] | None,
    ) -> Clause:
        if action is not None:
            return action.rule.clause
        clause_idx = key[0]
        if clause_idx is None:
            raise RuntimeError("source-less extension action has no matrix clause")
        return state.problem.matrix.clauses[clause_idx]

    def _push_frame(self, state: State, goal_id: int) -> Frame | None:
        frame = super()._push_frame(state, goal_id)
        if frame is None:
            return None
        if self._pending_path_limit_plan is None:
            return frame
        pending_goal_id, hits_before_action, terminal_hits = self._pending_path_limit_plan
        self._pending_path_limit_plan = None
        if pending_goal_id != frame.goal_id:
            return frame
        frame_id = id(frame)
        if hits_before_action:
            self._path_limit_hits_before_action[frame_id] = hits_before_action
        if terminal_hits:
            self._terminal_path_limit_hits[frame_id] = terminal_hits
        return frame

    def record_action_choice(self, state: State, action: Action) -> None:
        if not isinstance(action, ApplyAction) or not self._stack:
            super().record_action_choice(state, action)
            return
        frame = self._stack[-1]
        hits_by_action = self._path_limit_hits_before_action.get(id(frame))
        if hits_by_action is not None:
            self._record_path_limit_hits(hits_by_action.pop(id(action), 0))
        super().record_action_choice(state, action)

    def _backtrack_action(self, state: State) -> UndoAction | None:
        if self._stack:
            if not self._stack[-1].actions:
                self._record_terminal_path_limit_hits(self._stack[-1])
            self._pop_frame()
        if not self._stack:
            return None

        if self.backtrack == "maximal":
            while len(self._stack) > 1 and not self._stack[-1].actions:
                self._record_terminal_path_limit_hits(self._stack[-1])
                self._pop_frame()

        return self._undo_frame(state, len(self._stack) - 1)

    def _record_terminal_path_limit_hits(self, frame: Frame) -> None:
        self._record_path_limit_hits(
            self._terminal_path_limit_hits.pop(id(frame), 0)
        )

    def _pop_frame(self) -> Frame:
        frame = super()._pop_frame()
        frame_id = id(frame)
        self._path_limit_hits_before_action.pop(frame_id, None)
        self._terminal_path_limit_hits.pop(frame_id, None)
        return frame

    def _record_path_limit_hits(self, count: int) -> None:
        if count <= 0:
            return
        for _ in range(count):
            trace(trace_logger, "pathlim_hit")

    def available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if not self._stack:
                self._start_next_depth()
            actions = super().available_actions(state)
            if actions:
                return actions
            if not self._should_continue_after_empty_stack():
                return ()
            self._stack = []
            self._path_limit_hits_before_action.clear()
            self._terminal_path_limit_hits.clear()

    def _start_next_depth(self) -> None:
        previous_depth_limit = self.depth_limit
        self.depth_limit += 1
        self._path_limit_hit = False
        if previous_depth_limit > 0:
            trace(trace_logger, "pathlim")

    def _should_continue_after_empty_stack(self) -> bool:
        if self.comp is not None:
            if self.depth_limit >= self.comp:
                self.comp = None
                self.cut_enabled = False
                self.scut_enabled = False
                self.depth_limit = 0
            return True
        return self._path_limit_hit

    def no_action(self, state: State):
        return ProverOutcome.ID_FIXED_POINT


def _is_extension_action(action: Action) -> TypeGuard[ApplyAction[Extension]]:
    return isinstance(action, ApplyAction) and isinstance(action.rule, Extension)


__all__ = [
    "IterativeDeepeningOptions",
    "IterativeDeepeningPolicy",
]
