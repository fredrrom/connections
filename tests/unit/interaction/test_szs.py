from __future__ import annotations

from connections.interaction.outcome import ProverOutcome
from connections.interaction.szs import SZSStatus, to_szs_status


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
    for outcome in (ProverOutcome.EXHAUSTED,):
        assert (
            to_szs_status(outcome, has_conjecture=True)
            is SZSStatus.COUNTER_SATISFIABLE
        )
        assert (
            to_szs_status(outcome, has_conjecture=False)
            is SZSStatus.SATISFIABLE
        )


def test_no_success_outcome_maps_to_szs_no_success() -> None:
    # Both budgets are the prover's own allotment; Timeout and MemoryOut are
    # a supervising process's verdicts, and connections never concludes them.
    assert (
        to_szs_status(ProverOutcome.TIME_BUDGET, has_conjecture=True)
        is SZSStatus.RESOURCE_OUT
    )
    assert (
        to_szs_status(ProverOutcome.STEP_BUDGET, has_conjecture=True)
        is SZSStatus.RESOURCE_OUT
    )
    assert (
        to_szs_status(ProverOutcome.ERROR, has_conjecture=True)
        is SZSStatus.ERROR
    )
