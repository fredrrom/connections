"""The critic replays closed tableaux; failures indict the surface."""

from __future__ import annotations

import pytest

from connections.agent import AgentOptions, OnlineDFSAgent, OnlineIDAgent
from connections.environment.actions import ApplyAction
from connections.environment.dynamics import Dynamics
from connections.environment.state import State
from connections.environment.tableau import Tableau
from connections.interaction.rollout import rollout
from connections.interaction.run import Problem, build_state
from connections.interaction.strategy import MatrixOptions
from connections.syntax.formula import Atom, Function, Variable
from connections.syntax.matrix import Clause, Literal, Matrix

from conftest import first

from imitation.critic import (
    ObservationContext,
    ProofCloningCritic,
    ProofReplayError,
    replay_proof,
)
from imitation.performance import AllActionsMarkovAgent, PerformanceRecipe
from imitation.representation.schema import ACTION_KINDS

_KIND = {name: index for index, name in enumerate(ACTION_KINDS)}


def _lit(name: str, *args: str, neg: bool = False) -> Literal:
    terms = tuple(
        Variable(arg) if arg[:1].isupper() else Function(arg) for arg in args
    )
    return Literal(atom=Atom(name, terms), polarity=not neg)


def _closed_state(matrix: Matrix) -> State:
    state = State(matrix=matrix, tableau=Tableau())
    agent = OnlineDFSAgent(first)
    steps = 0
    while not state.tableau.root.closed:
        action = agent(state)
        assert isinstance(action, ApplyAction)
        Dynamics.transition(state, action)
        steps += 1
        assert steps < 20
    return state


def _dfs_recipe(**options: object) -> PerformanceRecipe:
    return PerformanceRecipe(
        agent_class=OnlineDFSAgent,
        options=AgentOptions(**options),  # type: ignore[arg-type]
    )


def test_a_fully_forced_proof_replays_and_yields_no_training_signal():
    matrix = Matrix(
        (
            Clause((_lit("p"),)),
            Clause((_lit("p", neg=True), _lit("q"), _lit("r"))),
            Clause((_lit("q", neg=True),)),
            Clause((_lit("r", neg=True),)),
        )
    )
    choices = replay_proof(recipe=_dfs_recipe(), closed_state=_closed_state(matrix))
    assert choices == (), "forced moves carry no decision, so nothing is recorded"


def test_a_reduction_step_replays_as_the_chosen_candidate():
    matrix = Matrix(
        (
            Clause((_lit("p"),)),
            Clause((_lit("p", neg=True), _lit("p", neg=True))),
        )
    )
    choices = replay_proof(recipe=_dfs_recipe(), closed_state=_closed_state(matrix))

    assert choices, "the proof passes at least one real decision"
    kinds = [
        choice.model_input.actions[choice.chosen_index][0] for choice in choices
    ]
    assert _KIND["reduction"] in kinds
    assert [c.trajectory_step_index for c in choices] == list(
        range(1, len(choices) + 1)
    )


def test_a_factorization_step_replays_as_the_chosen_candidate():
    matrix = Matrix(
        (
            Clause((_lit("p"), _lit("p"))),
            Clause((_lit("p", neg=True),)),
        )
    )
    choices = replay_proof(recipe=_dfs_recipe(), closed_state=_closed_state(matrix))

    kinds = [
        choice.model_input.actions[choice.chosen_index][0] for choice in choices
    ]
    assert _KIND["factorization"] in kinds


def test_a_surface_that_hides_the_proof_action_fails_the_replay():
    matrix = Matrix(
        (
            Clause((_lit("p"), _lit("p"))),
            Clause((_lit("p", neg=True),)),
        )
    )
    closed_state = _closed_state(matrix)

    with pytest.raises(ProofReplayError):
        replay_proof(
            recipe=_dfs_recipe(factorization="equal"),
            closed_state=closed_state,
        )


def test_the_wide_surface_shows_backtracks_alongside_the_proof_path():
    matrix = Matrix(
        (
            Clause((_lit("p"),)),
            Clause((_lit("p", neg=True), _lit("q"))),
            Clause((_lit("q", neg=True),)),
        )
    )
    recipe = PerformanceRecipe(agent_class=AllActionsMarkovAgent)
    choices = replay_proof(recipe=recipe, closed_state=_closed_state(matrix))

    assert choices, "undo candidates make later steps real decisions"
    assert all(
        choice.model_input.actions[choice.chosen_index][0] != _KIND["backtrack"]
        for choice in choices
    ), "the proof path never chooses a backtrack"
    assert any(
        row[0] == _KIND["backtrack"]
        for choice in choices
        for row in choice.model_input.actions
    ), "backtrack candidates appear in the shown lists"


def test_the_critic_labels_proofs_observed_from_a_rollout(tmp_path):
    problem = tmp_path / "either.p"
    problem.write_text(
        "fof(a0, axiom, p).\n"
        "fof(a1, axiom, p => q).\n"
        "fof(a2, axiom, r => q).\n"
        "fof(goal, conjecture, q).\n",
        encoding="utf-8",
    )
    recipe = PerformanceRecipe(agent_class=OnlineIDAgent)
    critic = ProofCloningCritic(recipe=recipe)

    state = build_state(Problem(problem), matrix_options=MatrixOptions())
    attempt = rollout(state, OnlineIDAgent(first), step_limit=100)
    critic.observe(
        attempt.state,
        ObservationContext(
            problem_path=str(problem), round_index=0, behavior_name="base"
        ),
    )

    examples = critic.feedback()
    assert examples, "the proof passes a two-way extension decision"
    assert not critic.failures
    for example in examples:
        assert 0 <= example.chosen_index < len(example.model_input.actions)
        assert example.surface_key == recipe.surface_key()
        assert example.round_index == 0
        assert example.behavior_name == "base"
        assert example.problem_path == str(problem)


def test_the_critic_ignores_states_that_are_not_proofs():
    matrix = Matrix((Clause((_lit("p"),)), Clause((_lit("q", neg=True),))))
    open_state = State(matrix=matrix, tableau=Tableau())
    critic = ProofCloningCritic(recipe=_dfs_recipe())

    critic.observe(open_state, ObservationContext(problem_path="open.p"))
    assert critic.feedback() == ()
    assert critic.failures == []


def test_the_critic_records_replay_failures_instead_of_repairing():
    matrix = Matrix(
        (
            Clause((_lit("p"), _lit("p"))),
            Clause((_lit("p", neg=True),)),
        )
    )
    closed_state = _closed_state(matrix)
    critic = ProofCloningCritic(recipe=_dfs_recipe(factorization="equal"))

    critic.observe(closed_state, ObservationContext(problem_path="fact.p"))
    assert critic.feedback() == ()
    assert len(critic.failures) == 1
    assert critic.failures[0].error_type == "ProofReplayError"
