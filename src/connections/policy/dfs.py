from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from connections.prover.status import ProverOutcome
from connections.policy.base import BacktrackGranularity, Policy
from connections.prover.actions import Action, ApplyAction
from connections.prover.dynamics import Dynamics
from connections.prover.rules import FactorizationMode, Start
from connections.prover.state import State
from connections.trace_logging import trace, trace_logger

DFSPolicyDecision = Action | ProverOutcome | None


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


class DFSPolicy(Policy):
    def __init__(
        self,
        *,
        cut: bool = False,
        scut: bool = False,
        backtrack: BacktrackGranularity = "step",
        factorization: FactorizationMode = "unify",
    ) -> None:
        self.cut_enabled = cut
        self.scut_enabled = scut
        self.backtrack = backtrack
        self.factorization = factorization
        self._stack: list[Frame] = []

    def __call__(self, state: State) -> DFSPolicyDecision:
        actions = self._available_actions(state)
        if not actions:
            return self._exhausted_outcome()
        action = self._next_action(state, actions)
        self._after_action(state, actions, action)
        return action

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        actions = self._prepare_actions(state)
        return () if actions is None else actions

    @abstractmethod
    def _next_action(self, state: State, actions: tuple[Action, ...]) -> Action:
        raise NotImplementedError

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

    def _exhausted_outcome(self) -> ProverOutcome:
        return ProverOutcome.DFS_EXHAUSTED

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


__all__ = [
    "ChoicepointFrame",
    "DFSPolicy",
    "Frame",
    "WorkFrame",
]
