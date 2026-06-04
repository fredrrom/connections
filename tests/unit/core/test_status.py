from __future__ import annotations

from connections.core.status import ProverOutcome, SZSStatus, to_szs_status


def test_proved_maps_by_problem_shape() -> None:
    assert (
        to_szs_status(
            ProverOutcome.PROVED,
            has_conjecture=True,
        )
        is SZSStatus.THEOREM
    )
    assert (
        to_szs_status(
            ProverOutcome.PROVED,
            has_conjecture=False,
        )
        is SZSStatus.UNSATISFIABLE
    )


def test_complete_negative_outcome_maps_by_problem_shape() -> None:
    for outcome in (ProverOutcome.ID_FIXED_POINT, ProverOutcome.DFS_EXHAUSTED):
        assert (
            to_szs_status(outcome, has_conjecture=True)
            is SZSStatus.COUNTER_SATISFIABLE
        )
        assert (
            to_szs_status(outcome, has_conjecture=False)
            is SZSStatus.SATISFIABLE
        )


def test_no_success_outcome_maps_to_szs_no_success() -> None:
    assert (
        to_szs_status(ProverOutcome.TIMEOUT, has_conjecture=True)
        is SZSStatus.TIMEOUT
    )
    assert (
        to_szs_status(ProverOutcome.STEP_BUDGET, has_conjecture=True)
        is SZSStatus.GAVE_UP
    )
    assert (
        to_szs_status(ProverOutcome.ERROR, has_conjecture=True)
        is SZSStatus.ERROR
    )
