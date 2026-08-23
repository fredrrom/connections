"""Depth-first search over the derivation.

The derivation fixes everything positional, so the search needs no stack of
its own: ``fringe[0]`` is the current goal, and the newest live rule
application is the step chronological backtracking undoes. What the
derivation cannot know is what was already tried, and that is the agent's
whole memory: the untried alternatives per goal, generated when the goal
first becomes current and deleted when the search abandons it. Deletion is
what keeps the dict honest: alternatives are only valid under the
constraints they were generated under, chronological undo restores exactly
those constraints whenever a goal is resumed, and a goal revisited after
abandonment is generated afresh. This is Prolog's backtracking, which is
why leanCoP is this agent's iterative-deepening subclass with a
first-action chooser.

The agent emits leanCoP's trace events at leanCoP's positions, the same way
the rollout emits one event per action: the trace logger decides whether
anyone is listening. Deferred events ride in the alternatives themselves as
``TraceToken`` entries, emitted when they surface at the head of what
remains -- which is exactly when leanCoP's candidate iteration would reach
them.
"""

from __future__ import annotations

from dataclasses import dataclass

from connections.agent.base import Agent, AgentOptions, AgentStatus, Chooser
from connections.environment.actions import Action, ApplyAction, UndoAction
from connections.environment.dynamics import Dynamics
from connections.environment.rules import Start
from connections.environment.state import State
from connections.trace_logging import trace, trace_logger


@dataclass(frozen=True, slots=True)
class TraceToken:
    """A deferred trace event queued between alternatives."""

    event: str


class OnlineDFSAgent(Agent):
    """Depth-first search with a chooser over the per-goal alternatives."""

    def __init__(
        self, choose: Chooser, options: AgentOptions | None = None
    ) -> None:
        super().__init__(options)
        self.choose = choose
        self._alternatives: dict[int, list[Action | TraceToken]] = {}
        self._committed: set[int] = set()
        self._scut_goal_id: int | None = None
        self._episode: State | None = None

    def __call__(self, state: State) -> Action | None:
        if state is not self._episode:
            # A new initial state is the environment's reset; the agent
            # notices from the percept. Derivation-bound memory dies here.
            self._episode = state
            self._on_new_episode()
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
        if isinstance(action, ApplyAction):
            self._alternatives[action.goal_id].remove(action)
        return action

    def _on_new_episode(self) -> None:
        self._alternatives.clear()
        self._committed.clear()
        self._scut_goal_id = None
        self.status = AgentStatus.SEARCHING

    def _exhaustion_status(self) -> AgentStatus:
        """What running out of actions means, given the options.

        Cut and scut prune parts of the space that may contain proofs, and
        conjecture start is incomplete when the axioms alone are
        contradictory. With any of them set, an empty frontier proves
        nothing, so the status is GAVE_UP rather than DFS_EXHAUSTED.
        """
        options = self.options
        if options.cut or options.scut or options.start != "positive":
            return AgentStatus.GAVE_UP
        return AgentStatus.DFS_EXHAUSTED

    # -- the search ---------------------------------------------------------

    def _available_actions(self, state: State) -> tuple[Action, ...]:
        while True:
            if self.options.cut:
                self._commit_closed(state)
            if state.tableau.root.closed:
                # The final call: backtracking here would undo the proof.
                return ()
            goal_id = state.fringe[0].goal_id
            alternatives = self._alternatives.get(goal_id)
            if alternatives is None:
                alternatives = list(self._actions_for_goal(state, goal_id))
                self._apply_scut(state, goal_id, alternatives)
                self._alternatives[goal_id] = alternatives
            while alternatives and isinstance(head := alternatives[0], TraceToken):
                del alternatives[0]
                trace(trace_logger, head.event)
            exposed = tuple(
                action
                for action in alternatives
                if not isinstance(action, TraceToken)
            )
            if exposed:
                return exposed
            self._forget(goal_id)
            actions = self._backtrack(state)
            if actions:
                return actions
            # The search is exhausted. An iterative agent may restart it.
            if not self._next_iteration():
                return ()
            self._alternatives.clear()
            self._committed.clear()
            self._scut_goal_id = None

    def _next_iteration(self) -> bool:
        return False

    def _actions_for_goal(
        self, state: State, goal_id: int
    ) -> tuple[Action | TraceToken, ...]:
        return Dynamics.apply_actions(
            state,
            state.tableau.goals[goal_id],
            factorization=self.options.factorization,
            start=self.options.start,
        ).ordered()

    def _backtrack(self, state: State) -> tuple[Action, ...]:
        app_id = self._backtrack_application(state)
        if app_id is None:
            return ()
        self._forget_subtree(state, app_id)
        return (UndoAction(app_id),)

    def _backtrack_application(self, state: State) -> int | None:
        """The step to undo: the newest, skipping committed subtrees.

        Under cut a committed goal's alternatives are gone, so unwinding its
        subtree step by step would only re-derive that; the undo jumps to the
        newest step whose goal can still be resumed, removing the committed
        subtree whole.
        """
        if self.options.backtrack == "maximal":
            ancestor_app_id = self._resumable_ancestor_application(state)
            if ancestor_app_id is not None:
                return ancestor_app_id
        applications = state.tableau.rule_applications
        for app_id in reversed(applications):
            if applications[app_id].parent_goal_id not in self._committed:
                return app_id
        return None

    def _resumable_ancestor_application(self, state: State) -> int | None:
        """The applied step of the nearest ancestor with untried alternatives."""
        goal = state.fringe[0]
        while goal.parent_rule_application_id is not None:
            parent_goal_id = state.tableau.rule_applications[
                goal.parent_rule_application_id
            ].parent_goal_id
            goal = state.tableau.goals[parent_goal_id]
            if self._alternatives.get(parent_goal_id):
                return goal.applied_rule_application_id
        return None

    def _forget_subtree(self, state: State, app_id: int) -> None:
        for child_goal_id in state.tableau.rule_applications[app_id].child_goal_ids:
            self._forget(child_goal_id)
            child_app_id = state.tableau.goals[child_goal_id].applied_rule_application_id
            if child_app_id is not None:
                self._forget_subtree(state, child_app_id)

    def _forget(self, goal_id: int) -> None:
        self._alternatives.pop(goal_id, None)
        self._committed.discard(goal_id)

    # -- cut and scut -------------------------------------------------------

    def _commit_closed(self, state: State) -> None:
        """leanCoP's cut: a closed goal's remaining alternatives are discarded."""
        for goal_id in reversed(self._alternatives):
            if goal_id in self._committed:
                continue
            goal = state.tableau.goals.get(goal_id)
            if goal is None or not goal.closed:
                continue
            self._committed.add(goal_id)
            self._alternatives[goal_id].clear()
            if goal_id != self._scut_goal_id:
                trace(trace_logger, "cut")

    def _apply_scut(
        self, state: State, goal_id: int, alternatives: list[Action | TraceToken]
    ) -> None:
        if not self.options.scut or goal_id != state.tableau.root_goal_id:
            return
        for action in alternatives:
            if isinstance(action, ApplyAction) and isinstance(action.rule, Start):
                alternatives[:] = [action]
                self._scut_goal_id = goal_id
                trace(trace_logger, "scut")
                return


__all__ = [
    "Chooser",
    "OnlineDFSAgent",
    "TraceToken",
]
