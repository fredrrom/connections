"""The performance element is a chooser; its contracts are the label space."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from connections.agent import AgentStatus, MarkovAgent, OnlineDFSAgent
from connections.environment.actions import ApplyAction, UndoAction
from connections.environment.dynamics import Dynamics
from connections.interaction.rollout import rollout
from connections.interaction.run import Problem, build_state
from connections.interaction.strategy import MatrixOptions

from conftest import REPO_ROOT

from imitation.performance import AllActionsMarkovAgent, ModelChooser
from imitation.representation.preprocess import GraphPreprocessor
from imitation.representation.schema import GraphInput


@dataclass
class _FirstIndexModel:
    """Scores nothing: always the first row. Records how often it was asked."""

    calls: int = 0
    inputs: list[GraphInput] = field(default_factory=list)

    def __call__(self, model_input: GraphInput) -> int:
        self.calls += 1
        self.inputs.append(model_input)
        return 0


@dataclass
class _OutOfRangeModel:
    def __call__(self, model_input: GraphInput) -> int:
        return len(model_input.actions)


def _socrates_state():
    return build_state(
        Problem(REPO_ROOT / "examples" / "socrates.p"),
        matrix_options=MatrixOptions(),
    )


def _chooser(model) -> ModelChooser:
    return ModelChooser(preprocess=GraphPreprocessor(), model=model)


def _decision_state(tmp_path):
    """A state whose current goal admits two extensions: a real decision."""

    problem = tmp_path / "either.p"
    problem.write_text(
        "fof(a1, axiom, p => q).\n"
        "fof(a2, axiom, r => q).\n"
        "fof(goal, conjecture, q).\n",
        encoding="utf-8",
    )
    state = build_state(Problem(problem), matrix_options=MatrixOptions())
    start = Dynamics.apply_actions(state, state.fringe[0]).ordered()
    assert len(start) == 1
    Dynamics.transition(state, start[0])
    actions = Dynamics.apply_actions(state, state.fringe[0]).ordered()
    assert len(actions) > 1, "the fixture must admit a real decision"
    return state, actions


def test_the_chooser_returns_the_indexed_candidate(tmp_path):
    state, actions = _decision_state(tmp_path)

    model = _FirstIndexModel()
    chosen = _chooser(model)(state, actions)
    assert chosen is actions[0]
    assert model.calls == 1
    assert len(model.inputs[0].actions) == len(actions)


def test_a_forced_move_skips_the_model():
    state = _socrates_state()
    action = Dynamics.apply_actions(state, state.fringe[0]).ordered()[0]

    model = _FirstIndexModel()
    chosen = _chooser(model)(state, (action,))
    assert chosen is action
    assert model.calls == 0, "a forced move carries no decision"


def test_an_out_of_range_index_raises_rather_than_wraps(tmp_path):
    state, actions = _decision_state(tmp_path)
    with pytest.raises(IndexError):
        _chooser(_OutOfRangeModel())(state, actions)


def test_the_wide_surface_lists_every_apply_action_then_undos_newest_first():
    state = _socrates_state()
    agent = AllActionsMarkovAgent(_chooser(_FirstIndexModel()))

    first = agent(state)
    assert isinstance(first, ApplyAction)
    Dynamics.transition(state, first)

    seen: list = []

    def recording(state, actions):
        seen.extend(actions)
        return actions[0]

    AllActionsMarkovAgent(recording)(state)
    apply_part = [a for a in seen if isinstance(a, ApplyAction)]
    undo_part = [a for a in seen if isinstance(a, UndoAction)]
    assert seen == apply_part + undo_part, "undos come after every apply action"
    expected_applies = [
        action
        for goal in state.fringe
        for action in Dynamics.apply_actions(state, goal).ordered()
    ]
    assert apply_part == expected_applies
    assert [u.step_id for u in undo_part] == sorted(
        state.tableau.rule_applications, reverse=True
    )


def test_the_wide_surface_agent_reports_closure_and_exhaustion():
    state = _socrates_state()
    agent = AllActionsMarkovAgent(lambda s, a: a[0])
    attempt = rollout(state, agent, step_limit=100)
    assert attempt.status is AgentStatus.CLOSED, "first-choice closes socrates"

    unprovable = build_state(
        Problem(REPO_ROOT / "examples" / "not_provable.p"),
        matrix_options=MatrixOptions(),
    )

    def no_undo(state, actions):
        applies = [a for a in actions if isinstance(a, ApplyAction)]
        return applies[0] if applies else actions[0]

    hopeless = AllActionsMarkovAgent(no_undo)
    result = rollout(unprovable, hopeless, step_limit=100)
    assert result.status in (AgentStatus.GAVE_UP, None), (
        "no proof exists: the agent gives up or the budget ends the attempt"
    )
    assert result.status is not AgentStatus.CLOSED


@pytest.mark.parametrize(
    "make_agent",
    [
        lambda choose: MarkovAgent(choose),
        lambda choose: OnlineDFSAgent(choose),
        lambda choose: AllActionsMarkovAgent(choose),
    ],
    ids=["markov", "dfs", "all-actions"],
)
def test_a_scripted_model_proves_socrates_inside_each_agent(make_agent):
    state = _socrates_state()
    agent = make_agent(_chooser(_FirstIndexModel()))
    attempt = rollout(state, agent, step_limit=200)
    assert attempt.status is AgentStatus.CLOSED
