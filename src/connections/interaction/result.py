"""What a run returns.

``Result`` is the entire data contract between ``connections`` and anything
built on it. It carries what only the run can know -- which strategy won, what
the SZS status is -- and nothing about the execution that produced it. Host,
wall time and provenance are facts about a run rather than about a proof, and
belong to whoever is recording them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from connections.agent import AgentStatus
from connections.interaction.outcome import ProverOutcome
from connections.interaction.strategy import Strategy
from connections.interaction.szs import SZSStatus

StrategyT = TypeVar("StrategyT", bound=Strategy)


@dataclass(frozen=True, slots=True)
class StrategyResult(Generic[StrategyT]):
    strategy: StrategyT
    outcome: ProverOutcome | None
    steps: int
    proof_size: int
    elapsed_seconds: float
    szs_status: SZSStatus | None = None
    agent_status: AgentStatus | None = None
    trajectory: tuple | None = None


@dataclass(frozen=True, slots=True)
class Result(Generic[StrategyT]):
    outcome: ProverOutcome | None
    strategy_results: tuple[StrategyResult[StrategyT], ...]
    winning_strategy_index: int | None = None
    szs_status: SZSStatus | None = None
    proof_payload: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """A JSON-able view. This is the whole serialisation contract.

        Anything else a caller wants recorded alongside -- host, wall time,
        policy version -- is a fact about the execution rather than the proof,
        and is the caller's to add.
        """
        return {
            "outcome": None if self.outcome is None else self.outcome.value,
            "szs_status": None if self.szs_status is None else self.szs_status.value,
            "winning_strategy_index": self.winning_strategy_index,
            "strategy_results": [
                {
                    "outcome": None if r.outcome is None else r.outcome.value,
                    "szs_status": None if r.szs_status is None else r.szs_status.value,
                    "steps": r.steps,
                    "proof_size": r.proof_size,
                    "agent_status": None
                    if r.agent_status is None
                    else r.agent_status.label,
                    "elapsed_seconds": r.elapsed_seconds,
                }
                for r in self.strategy_results
            ],
        }


__all__ = [
    "Result",
    "StrategyResult",
]
