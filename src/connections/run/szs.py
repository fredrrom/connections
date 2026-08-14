from __future__ import annotations

from enum import Enum

from connections.calculus.outcome import ProverOutcome


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
    if outcome in (ProverOutcome.STEP_BUDGET, ProverOutcome.TIME_BUDGET):
        # Both are the prover's own allotment running out, which is what
        # ResourceOut means. Timeout and MemoryOut are claims about a process
        # and belong to whatever supervises it: only a watching process can
        # make them, since its clock includes interpreter startup no in-process
        # timer sees, and a search killed for memory says nothing at all.
        return SZSStatus.RESOURCE_OUT
    if outcome is ProverOutcome.ERROR:
        return SZSStatus.ERROR
    return None


__all__ = [
    "SZSStatus",
    "to_szs_status",
]
