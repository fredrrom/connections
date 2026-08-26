"""The preprocessor writes the label space: one row per shown candidate."""

from __future__ import annotations

from connections.environment.actions import UndoAction
from connections.environment.dynamics import Dynamics
from connections.interaction.run import Problem, build_state
from connections.interaction.strategy import MatrixOptions

from conftest import REPO_ROOT

from imitation.representation.schema import ACTION_KINDS, GraphInput
from imitation.representation.preprocess import GraphPreprocessor

_KIND = {name: index for index, name in enumerate(ACTION_KINDS)}


def _socrates_state():
    return build_state(
        Problem(REPO_ROOT / "examples" / "socrates.p"),
        matrix_options=MatrixOptions(),
    )


def _start_actions(state):
    return Dynamics.apply_actions(state, state.fringe[0]).ordered()


def test_one_action_row_per_candidate_in_order():
    state = _socrates_state()
    actions = _start_actions(state)
    graph = GraphPreprocessor()(state, actions)

    assert len(graph.actions) == len(actions)
    assert all(row[0] == _KIND["start"] for row in graph.actions), (
        "an empty tableau admits start rules only"
    )
    assert graph.metadata["action_count"] == len(actions)
    assert graph.metadata["goal_count"] == len(state.tableau.goals)


def test_backtrack_rows_describe_undo_candidates():
    state = _socrates_state()
    preprocess = GraphPreprocessor()
    Dynamics.transition(state, _start_actions(state)[0])
    application_id = next(iter(state.tableau.rule_applications))

    actions = (*_start_actions(state), UndoAction(application_id))
    graph = preprocess(state, actions)
    assert graph.actions[-1][0] == _KIND["backtrack"]


def test_matrix_key_is_stable_per_matrix_and_fresh_across_matrices():
    state = _socrates_state()
    preprocess = GraphPreprocessor()
    first = preprocess(state, _start_actions(state))
    Dynamics.transition(state, _start_actions(state)[0])
    second = preprocess(state, Dynamics.apply_actions(state, state.fringe[0]).ordered())
    assert first.metadata["matrix_key"] == second.metadata["matrix_key"]

    other = build_state(
        Problem(REPO_ROOT / "examples" / "transitivity.p"),
        matrix_options=MatrixOptions(),
    )
    third = preprocess(other, _start_actions(other))
    assert third.metadata["matrix_key"] != first.metadata["matrix_key"]


def test_start_mode_changes_the_start_clause_feature(tmp_path):
    # The negative axiom clausifies to a positive clause, so the positive
    # start set is strictly larger than the conjecture start set.
    problem = tmp_path / "gap.p"
    problem.write_text(
        "fof(a1, axiom, ~s).\n"
        "fof(a2, axiom, q => p).\n"
        "fof(goal, conjecture, q).\n",
        encoding="utf-8",
    )
    state = build_state(
        Problem(problem),
        matrix_options=MatrixOptions(mark_conjecture=True),
    )
    positive = GraphPreprocessor(start="positive")(state, _start_actions(state))
    conjecture = GraphPreprocessor(start="conjecture")(state, _start_actions(state))

    assert [row[3] for row in positive.nodes["clause"]] != [
        row[3] for row in conjecture.nodes["clause"]
    ], "the is_start column tracks the start mode"


def test_a_real_graph_input_round_trips_through_json():
    state = _socrates_state()
    graph = GraphPreprocessor()(state, _start_actions(state))
    assert GraphInput.from_dict(graph.to_dict()) == graph
