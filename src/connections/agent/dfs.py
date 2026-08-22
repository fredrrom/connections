"""Depth-first search memory over the fringe-mirroring invariant.

The state is the source of truth, and this memory adds only what the state
cannot know: which alternatives remain untried per goal. One frame per goal,
the stack mirroring the ordered fringe -- the current goal is ``fringe[0]``,
and any disagreement between stack and state resolves to a single undo.

Two invariants keep this small. The memory is the sole actor: the rollout
applies exactly the action it returns, so after ``update`` the stack can track
the derivation with certainty, and no liveness re-derivation is needed. And
the memory emits no trace events: leanCoP's event choreography is pycop's
parity claim, carried by the traced memories there.
"""

from __future__ import annotations

from dataclasses import dataclass

from connections.agent.base import (
    AgentStatus,
    BacktrackGranularity,
    StartMode,
    start_clause_ids,
)
from connections.calculus.actions import Action, ApplyAction, UndoAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import FactorizationMode, Start
from connections.calculus.state import State


@dataclass(slots=True)
class Frame:
    goal_id: int
    actions: list[Action]


class DFSMemory:
    """leanCoP's search discipline as a memory: alternatives per goal."""

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

    # -- the Memory protocol ------------------------------------------------

    def exposed(self, state: State) -> tuple[Action, ...]:
        actions = self._available_actions(state)
        if not actions:
            self._status = (
                AgentStatus.CLOSED
                if state.tableau.root.closed
                else self._exhaustion_status()
            )
            return ()
        self._status = AgentStatus.SEARCHING
        return actions

    def update(self, state: State, action: Action) -> None:
        _ = state
        if not isinstance(action, ApplyAction):
            return
        frame = self._stack[-1]
        if frame.goal_id != action.goal_id:
            raise RuntimeError("selected action does not belong to the active frame")
        frame.actions.remove(action)

    def status(self) -> AgentStatus:
        return self._status

    def _exhaustion_status(self) -> AgentStatus:
        """The claim an empty frontier licenses, given this discipline.

        Cut and scut prune non-redundant parts of the space; conjecture start
        is incomplete when the axioms alone are contradictory. Any of them
        forfeits the exhaustion claim.
        """
        if self.cut_enabled or self.scut_enabled or self.start != "positive":
            return AgentStatus.GAVE_UP
        return AgentStatus.DFS_EXHAUSTED

    # -- the discipline -----------------------------------------------------

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                # The final call. The old prover never consulted the policy at
                # a closed state; the rollout does, and backtracking here would
                # undo the proof.
                return ()
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

    def _actions_for_goal(self, state: State, goal_id: int) -> tuple[Action, ...]:
        return Dynamics.apply_actions(
            state,
            state.tableau.goals[goal_id],
            factorization=self.factorization,
            start_ids=start_clause_ids(state.matrix, self.start),
        ).ordered()

    def _push_frame(self, state: State, goal_id: int) -> Frame | None:
        if goal_id not in state.tableau.goals:
            return None
        frame = Frame(
            goal_id=goal_id, actions=list(self._actions_for_goal(state, goal_id))
        )
        self._apply_scut(state, frame)
        self._stack.append(frame)
        return frame

    def _apply_scut(self, state: State, frame: Frame) -> None:
        if not self.scut_enabled or frame.goal_id != self._root_goal_id(state):
            return
        for action in frame.actions:
            if isinstance(action, ApplyAction) and isinstance(action.rule, Start):
                frame.actions = [action]
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
        del self._stack[frame_index + 1 :]
        goal = state.tableau.goals.get(self._stack[-1].goal_id)
        if goal is None:
            return None
        return Dynamics.get_undo(state, goal)

    def _discard_closed_frames(self, state: State) -> None:
        while self._stack:
            frame = self._stack[-1]
            goal = state.tableau.goals.get(frame.goal_id)
            if goal is not None and not goal.closed:
                return
            self._pop_frame()

    @staticmethod
    def _root_goal_id(state: State) -> int:
        return state.tableau.root_goal_id

    def _pop_frame(self) -> Frame:
        return self._stack.pop()


__all__ = [
    "DFSMemory",
    "Frame",
]
