from __future__ import annotations

from enum import Enum


class ProverOutcome(Enum):
    PROVED = "Proved"
    ID_FIXED_POINT = "IDFixedPoint"
    DFS_EXHAUSTED = "DFSExhausted"
    TIMEOUT = "Timeout"
    STEP_BUDGET = "StepBudget"
    TIME_BUDGET = "TimeBudget"
    MEMORY_OUT = "MemoryOut"
    ERROR = "Error"


__all__ = ["ProverOutcome"]
