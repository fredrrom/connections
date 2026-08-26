"""The experiment loop, the agent's barrier discipline, and their contract."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor


from connections.agent import AgentStatus, OnlineIDAgent
from connections.environment.state import State
from connections.environment.tableau import Tableau
from connections.interaction.rollout import rollout
from connections.interaction.run import Problem, build_state
from connections.interaction.strategy import MatrixOptions
from connections.syntax.formula import Atom
from connections.syntax.matrix import Clause, Literal, Matrix

from conftest import EITHER_VIA_P, EITHER_VIA_R

from imitation.actor_learner import DAggerAgent
from imitation.critic import ObservationContext
from imitation.experiment import evaluate, retention, run_experiment, solved_by_pass
from imitation.learning.trainer import SupervisedLearner, TrainingConfig
from imitation.model import GraphModelConfig, load_action_model
from imitation.performance import PerformanceRecipe
from imitation.records import choicepoint_key


def _agent(tmp_path, *, learning: bool = True) -> DAggerAgent:
    return DAggerAgent(
        PerformanceRecipe(agent_class=OnlineIDAgent),
        output_dir=tmp_path / "runs",
        learning=learning,
        learner=SupervisedLearner(
            model_config=GraphModelConfig(hidden_dim=32, message_rounds=3),
            training=TrainingConfig(
                epochs=200,
                learning_rate=5e-3,
                target_train_accuracy=1.0,
            ),
        ),
    )


def _problems(tmp_path) -> tuple[Problem, ...]:
    problems = []
    for name, text in (("via_p.p", EITHER_VIA_P), ("via_r.p", EITHER_VIA_R)):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        problems.append(Problem(path))
    return tuple(problems)


def test_dagger_trains_within_budget_and_halts_when_nothing_changes(tmp_path):
    agent = _agent(tmp_path)
    problems = _problems(tmp_path)

    report = run_experiment(
        agent, problems, horizon=200, total_steps=100_000
    )

    assert report.passes[0].solved == 2, "the base chooser solves the corpus"
    assert report.passes[-1].solved == 2, "the learned policy still solves it"
    assert agent.round_index >= 1, "at least one barrier update installed a model"
    assert agent.halted, "the run ended because a pass changed nothing"
    assert report.steps_spent == sum(
        record.measures.steps for record in report.records()
    )
    assert agent.checkpoints and agent.checkpoints[0].exists()
    assert set(report.proofs()) == {str(p.path) for p in problems}, (
        "the report carries a proof for every solved problem"
    )
    assert len(agent.task_status) == 2 and all(
        status is AgentStatus.CLOSED for status in agent.task_status.values()
    )


def test_the_budget_is_a_stopping_criterion_at_pass_boundaries(tmp_path):
    agent = _agent(tmp_path)
    report = run_experiment(
        _agent(tmp_path), _problems(tmp_path), horizon=200, total_steps=1
    )
    _ = agent
    assert len(report.passes) == 1, "the first pass exhausted the budget"


def test_learning_off_is_frozen_evaluation_of_the_same_agent(tmp_path):
    problems = _problems(tmp_path)
    frozen = _agent(tmp_path, learning=False)

    report = run_experiment(frozen, problems, horizon=200, total_steps=100_000)

    assert frozen.round_index == 0, "the guard never fires with learning off"
    assert frozen.model is None
    assert report.passes[0].solved == 2
    assert frozen.halted, "an unchanged pass halts the frozen agent too"


def test_evaluate_runs_a_frozen_policy_from_a_trained_agent(tmp_path):
    problems = _problems(tmp_path)
    agent = _agent(tmp_path)
    run_experiment(agent, problems, horizon=200, total_steps=100_000)
    assert agent.model is not None
    rounds = agent.round_index

    report = evaluate(agent.performance_copy, problems, horizon=200)
    assert report.passes[0].solved == 2
    assert agent.round_index == rounds, "evaluation moved nothing"


def test_serial_and_parallel_runs_are_observationally_equal(tmp_path):
    problems = _problems(tmp_path)
    serial = _agent(tmp_path / "serial")
    parallel = _agent(tmp_path / "parallel")

    serial_report = run_experiment(
        serial, problems, horizon=200, total_steps=100_000
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        parallel_report = run_experiment(
            parallel,
            problems,
            horizon=200,
            total_steps=100_000,
            executor=pool,
        )

    assert sorted(map(choicepoint_key, serial.experience())) == sorted(
        map(choicepoint_key, parallel.experience())
    ), "the same demonstrations were collected"
    assert serial.round_index == parallel.round_index
    assert serial.task_status == parallel.task_status
    assert serial_report.steps_spent == parallel_report.steps_spent

    serial_model = load_action_model(serial.checkpoints[-1])
    parallel_model = load_action_model(parallel.checkpoints[-1])
    for example in serial.experience():
        assert serial_model(example.model_input) == parallel_model(
            example.model_input
        ), "canonically ordered training fits the same model"


def test_episodes_per_problem_multiplies_the_wave(tmp_path):
    problems = _problems(tmp_path)
    report = run_experiment(
        _agent(tmp_path),
        problems,
        horizon=200,
        total_steps=1,
        episodes_per_problem=2,
    )
    indices = sorted(
        (record.problem_path, record.trajectory_index)
        for record in report.passes[0].records
    )
    assert indices == sorted(
        (str(problem.path), k) for problem in problems for k in (0, 1)
    )


def test_retention_reads_the_solved_sets_across_passes(tmp_path):
    problems = _problems(tmp_path)
    report = run_experiment(
        _agent(tmp_path), problems, horizon=200, total_steps=100_000
    )
    solved = solved_by_pass(report)
    assert all(len(s) == 2 for s in solved)
    for step in retention(report):
        assert step.lost == frozenset(), "no proofs were forfeited"
        assert step.kept == solved[0]


def test_the_agent_is_an_ordinary_agent_under_rollout(tmp_path):
    agent = _agent(tmp_path)
    problems = _problems(tmp_path)

    state = build_state(problems[0], matrix_options=MatrixOptions())
    attempt = rollout(state, agent, step_limit=200)
    assert attempt.status is AgentStatus.CLOSED
    assert agent.experience(), (
        "the closing state arrived as a percept and the critic stored it"
    )


def test_observing_a_non_proof_state_stores_nothing(tmp_path):
    agent = _agent(tmp_path)
    matrix = Matrix(
        (
            Clause((Literal(atom=Atom("p")),)),
            Clause((Literal(atom=Atom("q"), polarity=False),)),
        )
    )
    open_state = State(matrix=matrix, tableau=Tableau())

    agent.critic.observe(open_state, ObservationContext(problem_path="open.p"))
    assert agent.experience() == ()
