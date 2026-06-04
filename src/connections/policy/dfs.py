from __future__ import annotations

from dataclasses import dataclass

from connections.core.status import ProverOutcome
from connections.policy.base import (
    BacktrackGranularity,
    Policy,
)
from connections.prover.actions import Action, ApplyAction, UndoAction
from connections.prover.dynamics import Dynamics
from connections.prover.rules import FactorizationMode, Start
from connections.prover.state import State
from connections.trace_logging import trace, trace_logger


@dataclass(frozen=True, slots=True)
class DFSOptions:
    cut: bool = False
    scut: bool = False
    factorization: FactorizationMode = "unify"
    backtrack: BacktrackGranularity = "step"


@dataclass(slots=True)
class Frame:
    goal_id: int
    actions: list[Action]


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

    def available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if self.cut_enabled:
                self._discard_closed_frames(state)

            current_goal_id = None if not state.fringe else state.fringe[0].goal_id
            if current_goal_id is None:
                undo = self._backtrack_action(state)
                return () if undo is None else (undo,)

            if not self._stack:
                self._push_frame(state, current_goal_id)
                continue

            frame = self._stack[-1]
            if frame.goal_id != current_goal_id:
                if current_goal_id not in {old.goal_id for old in self._stack}:
                    self._push_frame(state, current_goal_id)
                    continue
                undo = self._backtrack_action(state)
                return () if undo is None else (undo,)

            goal = state.tableau.goals.get(frame.goal_id)
            if goal is None:
                self._pop_frame()
                continue
            if goal.closed:
                if self.cut_enabled:
                    self._discard_closed_frames(state)
                    continue
                undo = self._backtrack_action(state)
                return () if undo is None else (undo,)
            if goal.applied_rule_application_id is not None:
                undo = self._undo_frame(state, len(self._stack) - 1)
                return () if undo is None else (undo,)
            if not frame.actions:
                undo = self._backtrack_action(state)
                return () if undo is None else (undo,)
            return tuple(frame.actions)

    def next_action(self, state: State, actions: tuple[Action, ...]) -> Action:
        return self.choose(actions, 0)

    def no_action(self, state: State):
        return ProverOutcome.DFS_EXHAUSTED

    def record_action_choice(self, state: State, action: Action) -> None:
        if not isinstance(action, ApplyAction):
            return
        if not self._stack:
            raise RuntimeError("selected action has no active frame")
        frame = self._stack[-1]
        if frame.goal_id != action.goal_id:
            raise RuntimeError("selected action does not belong to the active frame")
        frame.actions.remove(action)

    def record_proof_found(self, state: State) -> None:
        if not self.cut_enabled:
            return
        root_goal_id = self._root_goal_id(state)
        for frame in reversed(self._stack):
            goal = state.tableau.goals.get(frame.goal_id)
            if goal is None or not goal.closed:
                continue
            if self.scut_enabled and frame.goal_id == root_goal_id:
                continue
            trace(trace_logger, "cut")

    def _push_frame(self, state: State, goal_id: int) -> Frame | None:
        if goal_id not in state.tableau.goals:
            return None
        frame = Frame(goal_id=goal_id, actions=list(self._actions_for_goal(state, goal_id)))
        self._apply_scut(state, frame)
        self._stack.append(frame)
        return frame

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

    def _apply_scut(self, state: State, frame: Frame) -> None:
        if not self.scut_enabled or frame.goal_id != self._root_goal_id(state):
            return
        for action in frame.actions:
            if isinstance(action, ApplyAction) and isinstance(action.rule, Start):
                frame.actions = [action]
                trace(trace_logger, "scut")
                return

    def _backtrack_action(self, state: State) -> UndoAction | None:
        if self._stack:
            self._pop_frame()
        if not self._stack:
            return None

        if self.backtrack == "maximal":
            while len(self._stack) > 1 and not self._stack[-1].actions:
                self._pop_frame()

        return self._undo_frame(state, len(self._stack) - 1)

    def _undo_frame(self, state: State, frame_index: int) -> UndoAction | None:
        self._discard_frames_after(frame_index)
        goal = state.tableau.goals.get(self._stack[-1].goal_id)
        if goal is None:
            return None
        return Dynamics.get_undo(state, goal)

    def _discard_closed_frames(self, state: State) -> None:
        root_goal_id = self._root_goal_id(state)
        while self._stack:
            frame = self._stack[-1]
            goal = state.tableau.goals.get(frame.goal_id)
            if goal is not None and not goal.closed:
                return
            if goal is not None and not (
                self.scut_enabled and frame.goal_id == root_goal_id
            ):
                trace(trace_logger, "cut")
            self._pop_frame()

    @staticmethod
    def _root_goal_id(state: State) -> int:
        return getattr(state.tableau, "root_goal_id", state.tableau.root.goal_id)

    def _pop_frame(self) -> Frame:
        return self._stack.pop()

    def _discard_frames_after(self, frame_index: int) -> None:
        del self._stack[frame_index + 1 :]


def create_dfs_policy(options: DFSOptions) -> DFSPolicy:
    return DFSPolicy(
        cut=options.cut,
        scut=options.scut,
        factorization=options.factorization,
        backtrack=options.backtrack,
    )


__all__ = [
    "DFSOptions",
    "DFSPolicy",
    "Frame",
    "create_dfs_policy",
]
