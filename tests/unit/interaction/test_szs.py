"""SZS straight from truncation and agent status."""

from __future__ import annotations

from connections.agent import AgentStatus
from connections.interaction.szs import SZSStatus, to_szs_status
from connections.interaction.truncation import Truncation


def test_closed_maps_by_problem_shape():
    assert (
        to_szs_status(None, AgentStatus.CLOSED, has_conjecture=True)
        is SZSStatus.THEOREM
    )
    assert (
        to_szs_status(None, AgentStatus.CLOSED, has_conjecture=False)
        is SZSStatus.UNSATISFIABLE
    )


def test_exhaustion_statuses_map_by_problem_shape():
    for status in (AgentStatus.DFS_EXHAUSTED, AgentStatus.ID_FIXED_POINT):
        assert (
            to_szs_status(None, status, has_conjecture=True)
            is SZSStatus.COUNTER_SATISFIABLE
        )
        assert (
            to_szs_status(None, status, has_conjecture=False)
            is SZSStatus.SATISFIABLE
        )


def test_truncation_is_resource_out_never_timeout():
    for truncation in (Truncation.STEPS, Truncation.TIME):
        assert (
            to_szs_status(truncation, None, has_conjecture=True)
            is SZSStatus.RESOURCE_OUT
        )


def test_no_claim_is_gave_up():
    for status in (AgentStatus.GAVE_UP, AgentStatus.SEARCHING, None):
        assert (
            to_szs_status(None, status, has_conjecture=True) is SZSStatus.GAVE_UP
        )
