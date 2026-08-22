"""What the prover concludes, in the prover's vocabulary.

Produced only by the judge in ``run``: agents speak ``AgentStatus``, rollouts
report observations, and the prover combines them with what it verified into
one of these. Nothing below ``run`` imports this module.
"""

from __future__ import annotations

from enum import Enum


class ProverOutcome(Enum):
    PROVED = "Proved"
    EXHAUSTED = "Exhausted"
    GAVE_UP = "GaveUp"
    STEP_BUDGET = "StepBudget"
    TIME_BUDGET = "TimeBudget"
    TIMEOUT = "Timeout"
    MEMORY_OUT = "MemoryOut"
    ERROR = "Error"


__all__ = ["ProverOutcome"]
