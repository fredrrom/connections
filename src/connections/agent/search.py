"""Depth-first search over the fringe-mirroring invariant.

The state is the source of truth, and this memory adds only what the state
cannot know: which alternatives remain untried per goal. One frame per goal,
the stack mirroring the ordered fringe -- the current goal is ``fringe[0]``,
and any disagreement between stack and state resolves to a single undo.

The stack is the agent's internal state, read against ``self.options`` and
reported through ``self.status``. It emits no trace events;
leanCoP's event choreography is pycop's parity claim, carried by the traced
memories there.
"""

from __future__ import annotations

from dataclasses import dataclass

from collections.abc import Callable, Sequence

from connections.agent.base import Agent, AgentOptions, AgentStatus
from connections.calculus.actions import Action, ApplyAction, UndoAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import Start
from connections.calculus.state import State


def start_clause_ids(matrix, mode: str) -> tuple[int, ...]:
    """The clauses an agent asks to start from.

    Selection is the agent's, like factorization: the matrix's role indexes
    are facts, which subset to query is the agent's option. "conjecture"
    falls back to the positive clauses when the matrix has no conjecture-role
    clauses, matching leanCoP.
    """
    if mode == "conjecture":
        return matrix.conjecture_clauses or matrix.positive_clauses
    return matrix.positive_clauses


@dataclass(slots=True)
class Frame:
    goal_id: int
    actions: list[Action]


Chooser = Callable[[State, Sequence[Action]], Action]


class OnlineDFSAgent(Agent):
    """Depth-first search over the fringe-mirroring stack, with a chooser."""

    def __init__(
        self, choose: Chooser, options: AgentOptions | None = None
    ) -> None:
        super().__init__(options)
        self.choose = choose
        self._stack: list[Frame] = []

    def __call__(self, state: State) -> Action | None:
        actions = self._available_actions(state)
        if not actions:
            self.status = (
                AgentStatus.CLOSED
                if state.tableau.root.closed
                else self._exhaustion_status()
            )
            return None
        self.status = AgentStatus.SEARCHING
        action = self.choose(state, actions)
        self._consume(action)
        return action

    def _consume(self, action: Action) -> None:
        if not isinstance(action, ApplyAction):
            return
        frame = self._stack[-1]
        if frame.goal_id != action.goal_id:
            raise RuntimeError("selected action does not belong to the active frame")
        frame.actions.remove(action)

    def _exhaustion_status(self) -> AgentStatus:
        """The claim an empty frontier licenses, given the agent's options.

        Cut and scut prune non-redundant parts of the space; conjecture start
        is incomplete when the axioms alone are contradictory. Any of them
        forfeits the exhaustion claim.
        """
        options = self.options
        if options.cut or options.scut or options.start != "positive":
            return AgentStatus.GAVE_UP
        return AgentStatus.DFS_EXHAUSTED

    # -- the search ---------------------------------------------------------

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if state.tableau.root.closed:
                # The final call: backtracking here would undo the proof.
                return ()
            if self.options.cut:
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
                self._stack.pop()
                continue
            if goal.closed:
                if self.options.cut:
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
            factorization=self.options.factorization,
            start_ids=start_clause_ids(state.matrix, self.options.start),
        ).ordered()

    def _push_frame(self, state: State, goal_id: int) -> Frame | None:
        if goal_id not in state.tableau.goals:
            return None
        frame = Frame(
            goal_id=goal_id,
            actions=list(self._actions_for_goal(state, goal_id)),
        )
        self._apply_scut(state, frame)
        self._stack.append(frame)
        return frame

    def _apply_scut(self, state: State, frame: Frame) -> None:
        if not self.options.scut or frame.goal_id != state.tableau.root_goal_id:
            return
        for action in frame.actions:
            if isinstance(action, ApplyAction) and isinstance(action.rule, Start):
                frame.actions = [action]
                return

    def _backtrack_action(self, state: State) -> UndoAction | None:
        if self._stack:
            self._stack.pop()
        if not self._stack:
            return None

        if self.options.backtrack == "maximal":
            while len(self._stack) > 1 and not self._stack[-1].actions:
                self._stack.pop()

        return self._undo_frame(state, len(self._stack) - 1)

    def _undo_frame(self, state: State, frame_index: int) -> UndoAction | None:
        del self._stack[frame_index + 1 :]
        goal = state.tableau.goals.get(self._stack[-1].goal_id)
        if goal is None:
            return None
        return Dynamics.get_undo(state, goal)

    def _discard_closed_frames(self, state: State) -> None:
        while self._stack:
            goal = state.tableau.goals.get(self._stack[-1].goal_id)
            if goal is not None and not goal.closed:
                return
            self._stack.pop()


__all__ = [
    "Chooser",
    "Frame",
    "OnlineDFSAgent",
    "start_clause_ids",
]
