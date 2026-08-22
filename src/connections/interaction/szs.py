"""SZS statuses, and the mapping from prover outcomes.

The split is by vocabulary, so the layers cannot contradict each other: a run
never says Timeout, a supervisor never says ResourceOut, and an agent never
says either.
"""

from __future__ import annotations

from enum import Enum

from connections.interaction.outcome import ProverOutcome


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


def to_szs_status(
    outcome: ProverOutcome | None,
    *,
    has_conjecture: bool | None,
) -> SZSStatus | None:
    if outcome is ProverOutcome.PROVED:
        if has_conjecture is None:
            return None
        return SZSStatus.THEOREM if has_conjecture else SZSStatus.UNSATISFIABLE
    if outcome is ProverOutcome.EXHAUSTED:
        # Only reachable through an agent's affirmative systematic claim.
        if has_conjecture is None:
            return None
        return (
            SZSStatus.COUNTER_SATISFIABLE
            if has_conjecture
            else SZSStatus.SATISFIABLE
        )
    if outcome is ProverOutcome.GAVE_UP:
        return SZSStatus.GAVE_UP
    if outcome in (ProverOutcome.STEP_BUDGET, ProverOutcome.TIME_BUDGET):
        # Both are the prover's own allotment running out, which is what
        # ResourceOut means. Timeout and MemoryOut are claims about a process
        # and belong to whatever supervises it.
        return SZSStatus.RESOURCE_OUT
    if outcome is ProverOutcome.ERROR:
        return SZSStatus.ERROR
    return None


__all__ = [
    "SZSStatus",
    "to_szs_status",
]
