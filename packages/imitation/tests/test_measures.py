"""The measures are identities over run records, not new bookkeeping."""

from __future__ import annotations

import pytest

from conftest import id_agent, id_strategy

from connections.interaction.records import StrategyResult
from connections.interaction.rollout import rollout
from connections.interaction.run import build_state, run_schedule
from connections.interaction.strategy import MatrixOptions, StrategySchedule
from connections.interaction.szs import SZSStatus

from imitation.experiment import (
    AttemptMeasures,
    aggregate,
    from_rollout,
    from_strategy_result,
    success_curve,
)


def _run_socrates(problem, steps):
    result = run_schedule(
        problem,
        schedule=StrategySchedule.single(id_strategy(), steps=steps),
    )
    return result.strategy_results[0]


def test_waste_and_directness_are_identities_on_a_real_proof(socrates_problem):
    strategy_result = _run_socrates(socrates_problem, steps=100)
    measures = from_strategy_result(strategy_result)

    assert measures.success, "socrates.p is a theorem within the budget"
    assert measures.proof_size is not None
    assert measures.waste == measures.steps - measures.proof_size
    assert measures.directness == measures.proof_size / measures.steps
    assert measures.elapsed_seconds == strategy_result.elapsed_seconds


def test_rollout_and_strategy_result_agree_on_the_same_agent(socrates_problem):
    strategy_result = _run_socrates(socrates_problem, steps=100)
    state = build_state(socrates_problem, matrix_options=MatrixOptions())
    attempt = rollout(state, id_agent(), step_limit=100)

    from_run = from_strategy_result(strategy_result)
    from_bare = from_rollout(attempt)
    assert from_bare.success == from_run.success
    assert from_bare.steps == from_run.steps
    assert from_bare.proof_size == from_run.proof_size
    assert from_bare.elapsed_seconds is None, "a bare rollout carries no timing"


def test_a_failed_attempt_carries_no_conditional_measures(socrates_problem):
    strategy_result = _run_socrates(socrates_problem, steps=1)
    measures = from_strategy_result(strategy_result)

    assert not measures.success
    assert measures.proof_size is None
    assert measures.directness is None
    assert measures.waste is None


def test_success_curve_matches_a_genuine_rerun_at_the_smaller_budget(
    socrates_problem,
):
    full = from_strategy_result(_run_socrates(socrates_problem, steps=100))
    closing_steps = full.steps

    curve = success_curve(
        [full],
        [closing_steps, closing_steps + 1, 100],
        run_budget=100,
    )
    assert curve == (0.0, 1.0, 1.0), "the curve turns just above the closing step"

    rerun_exact = from_strategy_result(
        _run_socrates(socrates_problem, steps=closing_steps)
    )
    rerun_above = from_strategy_result(
        _run_socrates(socrates_problem, steps=closing_steps + 1)
    )
    assert not rerun_exact.success, (
        "a budget of exactly T truncates before closure is observed"
    )
    assert rerun_above.success, "the rerun agrees with the curve above T"


def test_success_curve_refuses_budgets_beyond_the_runs(socrates_problem):
    measures = from_strategy_result(_run_socrates(socrates_problem, steps=50))
    with pytest.raises(ValueError):
        success_curve([measures], [51], run_budget=50)


def test_aggregate_over_no_successes_is_none_not_nan():
    failed = AttemptMeasures(
        success=False,
        steps=7,
        elapsed_seconds=None,
        proof_size=None,
        directness=None,
        waste=None,
    )
    corpus = aggregate([failed, failed])

    assert corpus.attempts == 2
    assert corpus.successes == 0
    assert corpus.j_s == 0.0
    assert corpus.j_t is None
    assert corpus.j_l is None
    assert corpus.j_d is None


def test_aggregate_means_condition_on_success():
    succeeded = AttemptMeasures(
        success=True,
        steps=10,
        elapsed_seconds=None,
        proof_size=5,
        directness=0.5,
        waste=5,
    )
    failed = AttemptMeasures(
        success=False,
        steps=10,
        elapsed_seconds=None,
        proof_size=None,
        directness=None,
        waste=None,
    )
    corpus = aggregate([succeeded, failed])

    assert corpus.j_s == 0.5
    assert corpus.j_t == 10
    assert corpus.j_l == 5
    assert corpus.j_d == 0.5


def test_a_success_larger_than_its_step_count_is_rejected():
    closed = StrategyResult(
        strategy=None,
        truncation=None,
        steps=3,
        proof_size=4,
        elapsed_seconds=0.0,
        szs_status=SZSStatus.THEOREM,
    )
    with pytest.raises(ValueError):
        from_strategy_result(closed)
