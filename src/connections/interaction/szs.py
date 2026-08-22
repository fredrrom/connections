"""SZS statuses, straight from what the rollout observed and the agent said.

The run reports SZS. The judge is this one function: a truncated episode is the prover's
own allotment running out, ResourceOut; the agent's statuses map to the success and
non-success verdicts; statuses absent from the map carry no claim and are
GaveUp. Timeout and MemoryOut are a supervising process's verdicts and are
never produced here.
"""

from __future__ import annotations

from enum import Enum

from connections.agent.base import AgentStatus
from connections.interaction.truncation import Truncation


class SZSStatus(str, Enum):
    THEOREM = "Theorem"
    CONTRADICTORY_AXIOMS = "ContradictoryAxioms"
    COUNTER_SATISFIABLE = "CounterSatisfiable"
    UNSATISFIABLE = "Unsatisfiable"
    SATISFIABLE = "Satisfiable"
    TIMEOUT = "Timeout"
    RESOURCE_OUT = "ResourceOut"
    MEMORY_OUT = "MemoryOut"
    GAVE_UP = "GaveUp"
    ERROR = "Error"


SUCCESS = frozenset({SZSStatus.THEOREM, SZSStatus.UNSATISFIABLE})
DECIDED = SUCCESS | frozenset(
    {SZSStatus.COUNTER_SATISFIABLE, SZSStatus.SATISFIABLE}
)


def to_szs_status(
    truncation: Truncation | None,
    status: AgentStatus | None,
    *,
    has_conjecture: bool | None,
) -> SZSStatus | None:
    if truncation is not None:
        return SZSStatus.RESOURCE_OUT
    if status is AgentStatus.CLOSED:
        if has_conjecture is None:
            return None
        return SZSStatus.THEOREM if has_conjecture else SZSStatus.UNSATISFIABLE
    if status in (AgentStatus.DFS_EXHAUSTED, AgentStatus.ID_FIXED_POINT):
        if has_conjecture is None:
            return None
        return (
            SZSStatus.COUNTER_SATISFIABLE
            if has_conjecture
            else SZSStatus.SATISFIABLE
        )
    return SZSStatus.GAVE_UP


__all__ = [
    "DECIDED",
    "SUCCESS",
    "SZSStatus",
    "to_szs_status",
]
