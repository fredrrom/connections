"""leanCoP-choreographed search memories: the trace-parity implementations.

These are the memories whose emitted trace events are bit-identical to the
bundled leanCoP family, verified by the parity harness. The choreography --
cut/scut/pathlim events at leanCoP's positions, and the deferred pathlim_hit
bookkeeping -- is what pycop's parity claim needs and the connections library
does not: the clean memories in connections.agent carry the same search
behaviour without the instrumentation, and test_memory_differential holds the
two together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

from connections.agent.base import (
    AgentStatus,
    BacktrackGranularity,
    StartMode,
    start_clause_ids,
)
from connections.agent.memory import ModelBasedAgent, first
from connections.calculus.actions import Action, ApplyAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import Extension, FactorizationMode, Start
from connections.calculus.state import State
from connections.syntax.matrix import Clause
from connections.trace_logging import trace, trace_logger

_MODAL_LOGICS = frozenset({"D", "T", "S4", "S5"})
ExtensionKey = tuple[int | None, int]

@dataclass(slots=True)
class WorkFrame:
    goal_ids: list[int]


@dataclass(slots=True)
class ChoicepointFrame:
    goal_id: int
    actions: list[Action]
    child_work_started: bool = False
    committed: bool = False
    trace_cut_on_close: bool = True


Frame = WorkFrame | ChoicepointFrame


class TracedDFSMemory:
    """leanCoP's search discipline as a memory: a stack of choicepoints.

    Everything here is the machinery that used to be DFSPolicy, moved rather
    than rewritten: ``exposed`` is the old action preparation, ``update`` the
    old post-action bookkeeping. What used to be the abstract _next_action is
    now a chooser supplied by whoever composes the agent.
    """

    def __init__(
        self,
        *,
        cut: bool = False,
        scut: bool = False,
        backtrack: BacktrackGranularity = "step",
        factorization: FactorizationMode = "unify",
        start: StartMode = "positive",
    ) -> None:
        self.cut_enabled = cut
        self.scut_enabled = scut
        self.backtrack = backtrack
        self.factorization = factorization
        self.start = start
        self._stack: list[Frame] = []
        self._status = AgentStatus.SEARCHING
        self._exposed_actions: tuple[Action, ...] = ()

    def exposed(self, state: State) -> tuple[Action, ...]:
        # _prepare_actions settles closed choicepoints on the way in, so the
        # call at a final state does this memory's shutdown before exposing
        # nothing.
        actions = self._available_actions(state)
        if not actions:
            self._status = (
                AgentStatus.CLOSED
                if state.tableau.root.closed
                else self._exhaustion_status()
            )
            return ()
        self._status = AgentStatus.SEARCHING
        self._exposed_actions = actions
        return actions

    def update(self, state: State, action: Action) -> None:
        self._after_action(state, self._exposed_actions, action)

    def status(self) -> AgentStatus:
        return self._status

    def _exhaustion_status(self) -> AgentStatus:
        """The claim an empty frontier licenses, given this discipline.

        Cut and scut prune non-redundant parts of the space; conjecture start
        is incomplete when the axioms alone are contradictory. Any of them
        forfeits the exhaustion claim: the search ran dry, but says nothing
        about the problem.
        """
        if self.cut_enabled or self.scut_enabled or self.start != "positive":
            return AgentStatus.GAVE_UP
        return AgentStatus.DFS_EXHAUSTED

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        actions = self._prepare_actions(state)
        return () if actions is None else actions

    def _after_action(
        self,
        state: State,
        actions: tuple[Action, ...],
        action: Action,
    ) -> None:
        _ = state, actions
        self._consume_choicepoint_action(action)

    def _on_tableau_closed(self, state: State) -> None:
        self._discard_deleted_choicepoints(state)
        self._commit_closed_choicepoints(state)

    def _choose_goal_id(self, state: State, goal_ids: tuple[int, ...]) -> int:
        _ = state
        return goal_ids[0]

    def _prepare_actions(self, state: State) -> tuple[Action, ...] | None:
        while True:
            self._discard_deleted_choicepoints(state)
            self._commit_closed_choicepoints(state)
            if state.tableau.root.closed:
                return None
            if not self._stack:
                self._stack.append(WorkFrame(self._initial_goal_ids(state)))

            if self._push_pending_work_from_choicepoint(state):
                continue

            work_frame_index = self._active_work_frame_index(state)
            if work_frame_index is not None:
                if self._activate_next_work_goal(state, work_frame_index):
                    continue
                backtrack = self._backtrack_or_retry(state)
                return backtrack

            retry = self._retry_actions(state)
            if retry is not None:
                return retry

            if (
                self.backtrack == "step"
                and not self._has_exhausted_open_choicepoint(state)
            ):
                undo = self._applied_choicepoint_undo(state)
                if undo is not None:
                    return undo

            backtrack = self._backtrack_or_retry(state)
            return backtrack

    def _active_work_frame_index(self, state: State) -> int | None:
        for index in range(len(self._stack) - 1, -1, -1):
            frame = self._stack[index]
            if isinstance(frame, WorkFrame):
                return index
            if self._choicepoint_is_live(state, frame):
                return None
        return None

    def _activate_next_work_goal(self, state: State, index: int) -> bool:
        frame = self._stack[index]
        if not isinstance(frame, WorkFrame):
            raise TypeError("active work frame index did not point to a work frame")
        open_goal_ids = self._open_goal_ids(state, frame.goal_ids)
        if not open_goal_ids:
            self._pop_frame(index)
            return True

        goal_id = self._choose_goal_id(state, open_goal_ids)
        if goal_id not in open_goal_ids:
            raise ValueError("chosen goal id is outside available goal ids")

        actions = list(self._actions_for_goal(state, goal_id))
        scut_applied = self._apply_scut(state, goal_id, actions)
        frame.goal_ids = [candidate for candidate in open_goal_ids if candidate != goal_id]
        choicepoint = ChoicepointFrame(
            goal_id=goal_id,
            actions=actions,
            trace_cut_on_close=not scut_applied,
        )
        self._stack.append(choicepoint)
        self._after_choicepoint_created(choicepoint)
        return True

    def _push_pending_work_from_choicepoint(self, state: State) -> bool:
        for index in range(len(self._stack) - 1, -1, -1):
            choicepoint = self._stack[index]
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            goal = state.tableau.goals.get(choicepoint.goal_id)
            if goal is None:
                continue
            if goal.closed:
                self._commit_if_cut(choicepoint)
                continue

            app_id = goal.applied_rule_application_id
            if (
                app_id is None
                or choicepoint.child_work_started
                or self._has_live_frame_above(state, index)
            ):
                continue
            choicepoint.child_work_started = True
            child_goal_ids = state.tableau.rule_applications[app_id].child_goal_ids
            if child_goal_ids:
                self._stack.append(WorkFrame(list(child_goal_ids)))
                return True
        return False

    def _retry_actions(self, state: State) -> tuple[Action, ...] | None:
        choicepoint = self._newest_open_choicepoint(state)
        if choicepoint is None or not choicepoint.actions:
            return None
        return tuple(choicepoint.actions)

    def _applied_choicepoint_undo(self, state: State) -> tuple[Action, ...] | None:
        for choicepoint in reversed(self._stack):
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            goal = state.tableau.goals.get(choicepoint.goal_id)
            if (
                goal is not None
                and not goal.closed
                and goal.applied_rule_application_id is not None
            ):
                undo = Dynamics.get_undo(state, goal)
                return None if undo is None else (undo,)
        return None

    def _has_exhausted_open_choicepoint(self, state: State) -> bool:
        for choicepoint in reversed(self._stack):
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            goal = state.tableau.goals.get(choicepoint.goal_id)
            if (
                goal is not None
                and not goal.closed
                and goal.applied_rule_application_id is None
                and not choicepoint.actions
            ):
                return True
        return False

    def _backtrack_or_retry(self, state: State) -> tuple[Action, ...] | None:
        while any(isinstance(frame, ChoicepointFrame) for frame in self._stack):
            index = self._backtrack_choicepoint_index(state)
            if index is None:
                return None
            while len(self._stack) > index + 1:
                self._pop_frame()
            choicepoint = self._stack[index]
            if not isinstance(choicepoint, ChoicepointFrame):
                raise TypeError("backtrack index did not point to a choicepoint")
            goal = state.tableau.goals.get(choicepoint.goal_id)
            if goal is None:
                self._pop_frame(index)
                continue
            if choicepoint.committed:
                self._pop_frame(index)
                continue
            if goal.applied_rule_application_id is not None:
                self._reset_choicepoint_attempt(choicepoint)
                undo = Dynamics.get_undo(state, goal)
                return None if undo is None else (undo,)
            if choicepoint.actions:
                self._reset_choicepoint_attempt(choicepoint)
                return tuple(choicepoint.actions)
            self._before_choicepoint_exhausted(choicepoint)
            self._pop_frame(index)
        return None

    def _backtrack_choicepoint_index(self, state: State) -> int | None:
        if self.backtrack == "maximal":
            for index, choicepoint in enumerate(self._stack):
                if not isinstance(choicepoint, ChoicepointFrame):
                    continue
                if choicepoint.committed:
                    continue
                if choicepoint.goal_id not in state.tableau.goals:
                    continue
                if choicepoint.actions:
                    return index
        for index in range(len(self._stack) - 1, -1, -1):
            choicepoint = self._stack[index]
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            if choicepoint.goal_id in state.tableau.goals:
                return index
        return None

    def _consume_choicepoint_action(self, action: Action) -> None:
        if not isinstance(action, ApplyAction):
            return
        choicepoint = self._newest_choicepoint_for_goal(action.goal_id)
        if choicepoint is None:
            raise RuntimeError("selected action has no active choicepoint")
        if action not in choicepoint.actions:
            raise RuntimeError("selected action does not belong to the active choicepoint")
        self._before_choicepoint_action(choicepoint, action)
        choicepoint.actions.remove(action)
        self._reset_choicepoint_attempt(choicepoint)

    def _newest_open_choicepoint(self, state: State) -> ChoicepointFrame | None:
        for choicepoint in reversed(self._stack):
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            goal = state.tableau.goals.get(choicepoint.goal_id)
            if goal is None or goal.closed:
                continue
            if goal.applied_rule_application_id is None:
                return choicepoint
        return None

    def _newest_choicepoint_for_goal(self, goal_id: int) -> ChoicepointFrame | None:
        for choicepoint in reversed(self._stack):
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            if choicepoint.goal_id == goal_id:
                return choicepoint
        return None

    def _reset_choicepoint_attempt(self, choicepoint: ChoicepointFrame) -> None:
        choicepoint.child_work_started = False
        choicepoint.committed = False

    def _actions_for_goal(
        self,
        state: State,
        goal_id: int,
    ) -> tuple[Action, ...]:
        return Dynamics.apply_actions(
            state,
            state.tableau.goals[goal_id],
            factorization=self.factorization,
            start_ids=start_clause_ids(state.matrix, self.start),
        ).ordered()

    def _after_choicepoint_created(self, choicepoint: ChoicepointFrame) -> None:
        _ = choicepoint

    def _before_choicepoint_action(
        self,
        choicepoint: ChoicepointFrame,
        action: Action,
    ) -> None:
        _ = choicepoint, action

    def _before_choicepoint_exhausted(self, choicepoint: ChoicepointFrame) -> None:
        _ = choicepoint

    def _before_choicepoint_removed(self, choicepoint: ChoicepointFrame) -> None:
        _ = choicepoint

    def _pop_frame(self, index: int = -1) -> Frame:
        frame = self._stack.pop(index)
        if isinstance(frame, ChoicepointFrame):
            self._before_choicepoint_removed(frame)
        return frame

    def _discard_deleted_choicepoints(self, state: State) -> None:
        index = 0
        while index < len(self._stack):
            frame = self._stack[index]
            if not isinstance(frame, ChoicepointFrame):
                index += 1
                continue
            if frame.goal_id in state.tableau.goals:
                index += 1
                continue
            self._pop_frame(index)

    def _commit_closed_choicepoints(self, state: State) -> None:
        for choicepoint in reversed(self._stack):
            if not isinstance(choicepoint, ChoicepointFrame):
                continue
            goal = state.tableau.goals.get(choicepoint.goal_id)
            if goal is not None and goal.closed:
                self._commit_if_cut(choicepoint)

    def _commit_if_cut(self, choicepoint: ChoicepointFrame) -> None:
        if not self.cut_enabled or choicepoint.committed:
            return
        if choicepoint.trace_cut_on_close:
            trace(trace_logger, "cut")
        choicepoint.actions.clear()
        choicepoint.committed = True

    def _apply_scut(
        self,
        state: State,
        goal_id: int,
        actions: list[Action],
    ) -> bool:
        if not self.scut_enabled or goal_id != self._root_goal_id(state):
            return False
        for action in actions:
            if isinstance(action, ApplyAction) and isinstance(action.rule, Start):
                actions[:] = [action]
                trace(trace_logger, "scut")
                return True
        return False

    def _open_goal_ids(self, state: State, goal_ids: list[int]) -> tuple[int, ...]:
        return tuple(
            goal_id
            for goal_id in goal_ids
            if self._is_open_unapplied_goal(state.tableau.goals.get(goal_id))
        )

    @staticmethod
    def _is_open_unapplied_goal(goal: object | None) -> bool:
        return (
            goal is not None
            and not getattr(goal, "closed")
            and getattr(goal, "applied_rule_application_id") is None
        )

    @staticmethod
    def _root_goal_id(state: State) -> int:
        return getattr(state.tableau, "root_goal_id", state.tableau.root.goal_id)

    def _initial_goal_ids(self, state: State) -> list[int]:
        root_goal_id = self._root_goal_id(state)
        if root_goal_id in state.tableau.goals:
            return [root_goal_id]
        return [goal.goal_id for goal in state.fringe if not goal.closed]

    def _reset_search(self) -> None:
        self._stack.clear()

    def _stack_empty(self) -> bool:
        return not self._stack

    def _has_live_frame_above(self, state: State, index: int) -> bool:
        return any(
            isinstance(frame, WorkFrame)
            or (
                isinstance(frame, ChoicepointFrame)
                and self._choicepoint_is_live(state, frame)
            )
            for frame in self._stack[index + 1 :]
        )

    @staticmethod
    def _choicepoint_is_live(state: State, choicepoint: ChoicepointFrame) -> bool:
        goal = state.tableau.goals.get(choicepoint.goal_id)
        return goal is not None and not goal.closed




@dataclass(frozen=True, slots=True)
class IterativeDeepeningOptions:
    comp: int | None = None
    initial_depth: int = 1


class TracedIDMemory(TracedDFSMemory):
    """Iterative deepening over the DFS memory: the depth ladder, comp
    switching, and the path-limit discipline that decides whether a fixed
    point may be claimed."""

    def __init__(
        self,
        *,
        cut: bool = False,
        scut: bool = False,
        comp: int | None = None,
        backtrack: BacktrackGranularity = "step",
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
                for rule in Dynamics.start_rules_for(
                    state, start_clause_ids(state.matrix, self.start)
                )
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
            for clause_idx, lit_idx in state.matrix.complements(
                goal.clause_idx,
                goal.literal_index,
            ):
                instance_id = state.fresh_instance_id()
                clause = state.matrix.clauses[clause_idx]
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
        if state.matrix.logic not in _MODAL_LOGICS:
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
        return state.matrix.clauses[clause_idx]

    def _after_choicepoint_created(self, choicepoint: ChoicepointFrame) -> None:
        if self._pending_path_limit_plan is None:
            return
        pending_goal_id, hits_before_action, terminal_hits = self._pending_path_limit_plan
        self._pending_path_limit_plan = None
        if pending_goal_id != choicepoint.goal_id:
            return
        key = id(choicepoint)
        if hits_before_action:
            self._path_limit_hits_before_action[key] = hits_before_action
        if terminal_hits:
            self._terminal_path_limit_hits[key] = terminal_hits

    def _before_choicepoint_action(
        self,
        choicepoint: ChoicepointFrame,
        action: Action,
    ) -> None:
        if not isinstance(action, ApplyAction):
            return
        hits_by_action = self._path_limit_hits_before_action.get(
            id(choicepoint)
        )
        if hits_by_action is not None:
            self._record_path_limit_hits(hits_by_action.pop(id(action), 0))

    def _before_choicepoint_exhausted(
        self,
        choicepoint: ChoicepointFrame,
    ) -> None:
        self._record_terminal_path_limit_hits(choicepoint)

    def _before_choicepoint_removed(self, choicepoint: ChoicepointFrame) -> None:
        key = id(choicepoint)
        self._path_limit_hits_before_action.pop(key, None)
        self._terminal_path_limit_hits.pop(key, None)

    def _record_terminal_path_limit_hits(
        self,
        choicepoint: ChoicepointFrame,
    ) -> None:
        self._record_path_limit_hits(
            self._terminal_path_limit_hits.pop(id(choicepoint), 0)
        )

    def _record_path_limit_hits(self, count: int) -> None:
        if count <= 0:
            return
        for _ in range(count):
            trace(trace_logger, "pathlim_hit")

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                # The final call: settle closed choicepoints and yield nothing.
                # Bumping the depth ladder at a closed root would be spurious
                # work and a spurious pathlim trace.
                return super()._available_actions(state)
            if self._stack_empty():
                self._start_next_depth()
            actions = super()._available_actions(state)
            if actions:
                return actions
            if not self._should_continue_after_empty_stack():
                return ()
            self._reset_search()
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

    def _exhaustion_status(self) -> AgentStatus:
        """A fixed point is claimable only from a complete final iteration.

        By the time the ladder stops, a comp() switch has already turned cut
        and scut off; if they are still on, the space was pruned and the claim
        is forfeit. The path-limit condition -- the bound never bound during
        the exhausting iteration -- is what _should_continue_after_empty_stack
        already required to stop at all.
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


def traced_leancop_agent(**options) -> ModelBasedAgent:
    """leanCoP's agent: iterative-deepening memory, first-choice chooser."""
    return ModelBasedAgent(TracedIDMemory(**options), first)




__all__ = [
    "TracedDFSMemory",
    "TracedIDMemory",
    "traced_leancop_agent",
]
