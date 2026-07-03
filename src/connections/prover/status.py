from __future__ import annotations

from enum import Enum


class ProverOutcome(Enum):
    PROVED = "Proved"
    ID_FIXED_POINT = "IDFixedPoint"
    DFS_EXHAUSTED = "DFSExhausted"
    TIMEOUT = "Timeout"
    STEP_BUDGET = "StepBudget"
    MEMORY_OUT = "MemoryOut"
    ERROR = "Error"


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
    if outcome in (ProverOutcome.ID_FIXED_POINT, ProverOutcome.DFS_EXHAUSTED):
        if has_conjecture is None:
            return None
        return (
            SZSStatus.COUNTER_SATISFIABLE
            if has_conjecture
            else SZSStatus.SATISFIABLE
        )
    if outcome is ProverOutcome.TIMEOUT:
        return SZSStatus.TIMEOUT
    if outcome is ProverOutcome.MEMORY_OUT:
        return SZSStatus.MEMORY_OUT
    if outcome is ProverOutcome.STEP_BUDGET:
        # The step budget is the prover's own resource; exhausting it is a
        # ResourceOut in SZS terms. Wall-clock and memory verdicts (Timeout,
        # MemoryOut) belong to whatever supervises the prover process.
        return SZSStatus.RESOURCE_OUT
    if outcome is ProverOutcome.ERROR:
        return SZSStatus.ERROR
    return None


__all__ = [
    "ProverOutcome",
    "SZSStatus",
    "to_szs_status",
]
