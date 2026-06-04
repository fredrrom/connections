from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from connections.core.status import ProverOutcome, SZSStatus
from connections.prover.prover import ProverResult


@dataclass(frozen=True, slots=True)
class CorpusRunRow:
    problem: str
    path: str
    status: str | None
    outcome: str | None
    szs_status: str | None
    inference_actions: int
    elapsed_seconds: float
    strategy_count: int
    winning_strategy_index: int | None
    error_type: str | None = None
    error_message: str | None = None


def row_from_result(
    path: str | Path,
    result: ProverResult[Any],
    *,
    problem: str | None = None,
) -> CorpusRunRow:
    return CorpusRunRow(
        problem=problem or Path(path).name,
        path=str(path),
        status=_status_value(result.szs_status),
        outcome=_outcome_value(result.outcome),
        szs_status=_status_value(result.szs_status),
        inference_actions=sum(
            strategy.inference_actions for strategy in result.strategy_results
        ),
        elapsed_seconds=sum(
            strategy.elapsed_seconds for strategy in result.strategy_results
        ),
        strategy_count=len(result.strategy_results),
        winning_strategy_index=result.winning_strategy_index,
    )


def row_from_error(
    path: str | Path,
    error: BaseException,
    *,
    problem: str | None = None,
) -> CorpusRunRow:
    return CorpusRunRow(
        problem=problem or Path(path).name,
        path=str(path),
        status=SZSStatus.ERROR.value,
        outcome=ProverOutcome.ERROR.value,
        szs_status=SZSStatus.ERROR.value,
        inference_actions=0,
        elapsed_seconds=0.0,
        strategy_count=0,
        winning_strategy_index=None,
        error_type=type(error).__name__,
        error_message=str(error),
    )


def row_to_json(row: CorpusRunRow) -> dict[str, object]:
    return {
        "problem": row.problem,
        "path": row.path,
        "status": row.status,
        "outcome": row.outcome,
        "szs_status": row.szs_status,
        "inference_actions": row.inference_actions,
        "elapsed_seconds": row.elapsed_seconds,
        "strategy_count": row.strategy_count,
        "winning_strategy_index": row.winning_strategy_index,
        "error_type": row.error_type,
        "error_message": row.error_message,
    }


def row_to_json_line(row: CorpusRunRow) -> str:
    return json.dumps(row_to_json(row), sort_keys=True)


def _status_value(status: SZSStatus | None) -> str | None:
    return None if status is None else status.value


def _outcome_value(outcome: ProverOutcome | None) -> str | None:
    return None if outcome is None else outcome.value


__all__ = [
    "CorpusRunRow",
    "row_from_error",
    "row_from_result",
    "row_to_json",
    "row_to_json_line",
]
