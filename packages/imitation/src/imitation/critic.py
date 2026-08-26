"""The critic: judging observed states against the performance standard.

The standard is proofhood -- s |- omega, decided by the calculus, outside
the agent. The critic observes states, keeps the ones that are proof
states, and turns each into task-conditioned feedback for the learning
element: a labeled demonstration, produced by replaying the closed tableau
as a trajectory of the target surface. Replay is the same agent the
performance element uses under a perfectly informed chooser -- the
``ReplayChooser`` picks, at every choicepoint, the shown candidate that
matches an unused goal of the closed proof. Failures are diagnostic, never
repaired: they indict the surface (options that hide the proof action) or
the matcher, and the caller records them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from collections.abc import Sequence

from connections.environment.actions import Action, ApplyAction
from connections.environment.dynamics import Dynamics
from connections.environment.rules import Extension, Factorization, Reduction, Rule, Start
from connections.environment.state import State
from connections.environment.tableau import Tableau

from imitation.performance import PerformanceRecipe
from imitation.records import Example, ReplayFailure
from imitation.representation.schema import GraphInput


logger = logging.getLogger(__name__)


class ProofReplayError(RuntimeError):
    """A closed tableau the target surface could not reconstruct."""


@dataclass(frozen=True, slots=True)
class Choicepoint:
    """One recorded decision of a replay: the shown input and the pick."""

    trajectory_step_index: int
    proof_step_index: int
    model_input: GraphInput
    chosen_index: int


@dataclass(slots=True)
class ReplayChooser:
    """The perfectly informed chooser: pick the proof action, record it.

    At each call it finds the first shown candidate that matches an unused
    closed-tableau goal -- address plus rule identity -- records the
    decision when there was one to make (a forced move carries no decision,
    matching the acting chooser's shortcut), and returns the action.
    """

    closed_state: State
    recipe: PerformanceRecipe
    proof_goal_ids: tuple[int, ...]
    used_goal_ids: set[int] = field(default_factory=set)
    choices: list[Choicepoint] = field(default_factory=list)
    last_closed_goal_id: int | None = None

    def __call__(self, state: State, actions: Sequence[Action]) -> Action:
        chosen_index, closed_goal_id, proof_step_index = self._match(state, actions)
        if len(actions) > 1:
            self.choices.append(
                Choicepoint(
                    trajectory_step_index=len(self.choices) + 1,
                    proof_step_index=proof_step_index,
                    model_input=self.recipe.preprocess(state, actions),
                    chosen_index=chosen_index,
                )
            )
        self.used_goal_ids.add(closed_goal_id)
        self.last_closed_goal_id = closed_goal_id
        return actions[chosen_index]

    def _match(
        self, state: State, actions: Sequence[Action]
    ) -> tuple[int, int, int]:
        for action_index, action in enumerate(actions):
            for proof_index, closed_goal_id in enumerate(self.proof_goal_ids, start=1):
                if closed_goal_id in self.used_goal_ids:
                    continue
                if _action_matches_closed_goal(
                    state,
                    closed_state=self.closed_state,
                    action=action,
                    closed_goal_id=closed_goal_id,
                ):
                    return action_index, closed_goal_id, proof_index
        raise ProofReplayError(
            "the target surface did not expose any enabled proof action"
        )


def replay_proof(
    *, recipe: PerformanceRecipe, closed_state: State
) -> tuple[Choicepoint, ...]:
    """Reconstruct the closed tableau as a trajectory of the target surface.

    A fresh state on the same matrix, the recipe's agent under the replay
    chooser, and per-step validation that the installed rule application's
    children match the closed proof's. The depth bound is normalized to
    cover the proof, since replay teaches choices, not depth schedules.
    """

    if not closed_state.tableau.root.closed:
        raise ProofReplayError("cannot replay an open tableau")

    replay_state = State(matrix=closed_state.matrix, tableau=Tableau())
    chooser = ReplayChooser(
        closed_state=closed_state,
        recipe=recipe,
        proof_goal_ids=_closed_proof_goal_ids(closed_state),
    )
    depth = max(
        (goal.depth for goal in closed_state.tableau.goals.values()), default=0
    )
    agent = recipe.with_chooser(chooser, initial_depth=depth + 2)

    while not replay_state.tableau.root.closed:
        action = agent(replay_state)
        if not isinstance(action, ApplyAction):
            raise ProofReplayError(
                "replay reached a state with no proof action to apply"
            )
        closed_goal_id = chooser.last_closed_goal_id
        if closed_goal_id is None:
            raise ProofReplayError("the replay chooser recorded no closed goal")
        Dynamics.transition(replay_state, action)
        _validate_child_addresses(replay_state, action, closed_state, closed_goal_id)
        chooser.last_closed_goal_id = None

    if len(chooser.used_goal_ids) != len(chooser.proof_goal_ids):
        raise ProofReplayError(
            "replay closed before every closed-tableau step was used"
        )
    return tuple(chooser.choices)


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """Where an observation came from: provenance stamped on the feedback."""

    problem_path: str
    round_index: int | None = None
    behavior_name: str | None = None


@dataclass(slots=True)
class ProofCloningCritic:
    """The critic of proof cloning: proofhood in, demonstrations out."""

    recipe: PerformanceRecipe
    examples: list[Example] = field(default_factory=list)
    failures: list[ReplayFailure] = field(default_factory=list)

    def observe(self, state: State, context: ObservationContext) -> None:
        """Score a state against the standard; store it if it is a proof."""

        if not state.tableau.root.closed:
            return
        surface_key = self.recipe.surface_key()
        try:
            choices = replay_proof(recipe=self.recipe, closed_state=state)
        except ProofReplayError as error:
            logger.warning(
                "replay failed on %s: %s", context.problem_path, error
            )
            self.failures.append(
                ReplayFailure(
                    problem_path=context.problem_path,
                    surface_key=surface_key,
                    error_type=type(error).__name__,
                    message=str(error),
                    round_index=context.round_index,
                    behavior_name=context.behavior_name,
                )
            )
            return
        self.examples.extend(
            Example(
                problem_path=context.problem_path,
                trajectory_step_index=choice.trajectory_step_index,
                proof_step_index=choice.proof_step_index,
                surface_key=surface_key,
                model_input=choice.model_input,
                chosen_index=choice.chosen_index,
                round_index=context.round_index,
                behavior_name=context.behavior_name,
            )
            for choice in choices
        )

    def feedback(self) -> tuple[Example, ...]:
        return tuple(self.examples)


def _action_matches_closed_goal(
    state: State,
    *,
    closed_state: State,
    action: Action,
    closed_goal_id: int,
) -> bool:
    if not isinstance(action, ApplyAction):
        return False
    goal = state.tableau.goals.get(action.goal_id)
    closed_goal = closed_state.tableau.goals[closed_goal_id]
    if goal is None or goal.address != closed_goal.address:
        return False
    closed_app_id = closed_goal.applied_rule_application_id
    if closed_app_id is None:
        return False
    return _rules_match(
        state,
        closed_state=closed_state,
        rule=action.rule,
        closed_rule=closed_state.tableau.rule_applications[closed_app_id].rule,
    )


def _rules_match(
    state: State,
    *,
    closed_state: State,
    rule: Rule,
    closed_rule: Rule,
) -> bool:
    if isinstance(rule, Start) and isinstance(closed_rule, Start):
        return rule.clause_idx == closed_rule.clause_idx
    if isinstance(rule, Extension) and isinstance(closed_rule, Extension):
        return (
            rule.clause_idx == closed_rule.clause_idx
            and rule.lit_idx == closed_rule.lit_idx
        )
    if isinstance(rule, Reduction) and isinstance(closed_rule, Reduction):
        return _goal_address(state, rule.source_goal_id) == _goal_address(
            closed_state, closed_rule.source_goal_id
        )
    if isinstance(rule, Factorization) and isinstance(closed_rule, Factorization):
        return rule.mode == closed_rule.mode and _goal_address(
            state, rule.source_goal_id
        ) == _goal_address(closed_state, closed_rule.source_goal_id)
    return False


def _validate_child_addresses(
    state: State,
    action: ApplyAction,
    closed_state: State,
    closed_goal_id: int,
) -> None:
    goal = state.tableau.goals.get(action.goal_id)
    if goal is None or goal.applied_rule_application_id is None:
        raise ProofReplayError("the replayed action installed no rule application")
    application = state.tableau.rule_applications[goal.applied_rule_application_id]
    closed_goal = closed_state.tableau.goals[closed_goal_id]
    closed_app_id = closed_goal.applied_rule_application_id
    if closed_app_id is None:
        raise ProofReplayError("the closed proof goal has no rule application")
    closed_application = closed_state.tableau.rule_applications[closed_app_id]
    child_addresses = tuple(
        state.tableau.goals[child_id].address
        for child_id in application.child_goal_ids
    )
    closed_child_addresses = tuple(
        closed_state.tableau.goals[child_id].address
        for child_id in closed_application.child_goal_ids
    )
    if child_addresses != closed_child_addresses:
        raise ProofReplayError("replay produced unexpected child addresses")


def _closed_proof_goal_ids(state: State) -> tuple[int, ...]:
    goal_ids: list[int] = []

    def visit(goal_id: int) -> None:
        goal = state.tableau.goals[goal_id]
        application_id = goal.applied_rule_application_id
        if application_id is None:
            return
        goal_ids.append(goal_id)
        for child_id in state.tableau.rule_applications[application_id].child_goal_ids:
            visit(child_id)

    visit(state.tableau.root_goal_id)
    return tuple(goal_ids)


def _goal_address(state: State, goal_id: int) -> tuple[int, ...] | None:
    goal = state.tableau.goals.get(goal_id)
    return None if goal is None else goal.address


__all__ = [
    "Choicepoint",
    "ObservationContext",
    "ProofCloningCritic",
    "ProofReplayError",
    "ReplayChooser",
    "replay_proof",
]
