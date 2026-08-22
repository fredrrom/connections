from __future__ import annotations

import cProfile
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import pstats
from typing import Any

from pycop.runs.run_corpus import (
    RunRow,
    row_to_json,
)

RunRows = Callable[[], Iterable[RunRow]]


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    output_dir: str | Path
    sort: str = "cumulative"
    limit_functions: int = 40
    metadata: dict[str, Any] | None = None
    write_summary: bool = True


def profile_run_rows(
    run_rows: RunRows,
    config: ProfileConfig,
) -> dict[str, object]:
    output = Path(config.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    profile_path = output / "profile.pstats"
    runs_jsonl_path = output / "runs.jsonl"

    profiler = cProfile.Profile()
    profiler.enable()
    rows = [_profile_row(row) for row in run_rows()]
    profiler.disable()
    profiler.dump_stats(profile_path)
    _write_jsonl(runs_jsonl_path, rows)

    summary = summarize_profile(
        profile_path,
        output_dir=output,
        run_rows=rows,
        sort=config.sort,
        limit_functions=config.limit_functions,
        metadata=config.metadata,
        runs_jsonl_path=runs_jsonl_path,
    )
    if config.write_summary:
        _write_json(output / "summary.json", summary)

    return {
        "schema": "connections.runs_profile_run.v1",
        "profile_path": str(profile_path),
        "runs_jsonl_path": str(runs_jsonl_path),
        "output_dir": str(output),
        "rows": len(rows),
        "summary": summary,
    }


def summarize_profile(
    profile_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    run_rows: Sequence[dict[str, Any]] | None = None,
    sort: str = "cumulative",
    limit_functions: int = 40,
    settings: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    runs_jsonl_path: str | Path | None = None,
    benchmark_name: str | None = None,
    benchmark_source: str | Path | None = None,
    source_file_dirs: Sequence[str | Path] = (),
) -> dict[str, object]:
    profile = Path(profile_path)
    output = Path(output_dir) if output_dir is not None else profile.parent
    output.mkdir(parents=True, exist_ok=True)
    extra_metadata = metadata or {}

    stats = pstats.Stats(str(profile)).strip_dirs().sort_stats(sort)
    total_seconds = float(getattr(stats, "total_tt", 0.0))
    total_calls = int(getattr(stats, "total_calls", 0))
    primitive_calls = int(getattr(stats, "prim_calls", 0))
    functions = _profile_functions(stats, limit_functions)
    all_functions = _profile_functions(stats, None)
    callers = _profile_callers(stats)
    functions_path = output / "profile_functions.jsonl"
    callers_path = output / "profile_callers.jsonl"
    overview_path = output / "profile_overview.json"
    _write_jsonl(functions_path, all_functions)
    _write_jsonl(callers_path, callers)

    rows = list(run_rows or ())
    overview = {
        **extra_metadata,
        **build_profile_overview(
            rows,
            profile_total_seconds=total_seconds,
        ),
    }
    _write_json(overview_path, overview)

    summary: dict[str, object] = {
        "schema": "connections.runs_profile_summary.v1",
        "kind": "runs_profile",
        **extra_metadata,
        "profile_path": str(profile),
        "profile_overview_path": str(overview_path),
        "profile_functions_path": str(functions_path),
        "profile_callers_path": str(callers_path),
        "sort": sort,
        "limit_functions": limit_functions,
        "total_calls": total_calls,
        "primitive_calls": primitive_calls,
        "total_seconds": total_seconds,
        "functions": functions,
        "overview": overview,
        "benchmark": {
            "name": benchmark_name,
            "source": None if benchmark_source is None else str(benchmark_source),
            "source_file_dirs": [str(path) for path in source_file_dirs],
        },
        "settings": list(settings),
    }
    if runs_jsonl_path is not None:
        summary["runs_jsonl_path"] = str(runs_jsonl_path)
    return summary


def build_profile_overview(
    rows: Sequence[dict[str, Any]],
    *,
    profile_total_seconds: float,
) -> dict[str, Any]:
    elapsed_values = _numbers(rows, "elapsed_seconds")
    inference_values = _numbers(rows, "steps")
    status_counts = Counter(str(row.get("status", "UNKNOWN")) for row in rows)
    timeout_rows = [
        row
        for row in rows
        if "limit" in str(row.get("status", "")).lower()
        or "timeout" in str(row.get("status", "")).lower()
    ]
    error_rows = [
        row for row in rows if "error" in str(row.get("status", "")).lower()
    ]
    overview: dict[str, Any] = {
        "schema": "connections.runs_profile_overview.v1",
        "total_elapsed_seconds": sum(elapsed_values)
        if elapsed_values
        else profile_total_seconds,
        "profile_total_seconds": profile_total_seconds,
        "status_counts": dict(sorted(status_counts.items())),
        "elapsed_seconds": _profile_quantiles(elapsed_values),
        "steps": {
            "total": sum(inference_values) if inference_values else None,
            "mean": sum(inference_values) / len(inference_values)
            if inference_values
            else None,
        },
        "slowest_problems": _problem_rows(
            sorted(
                rows,
                key=lambda row: _number_or_zero(row.get("elapsed_seconds")),
                reverse=True,
            )[:25]
        ),
        "timeout_problems": _problem_rows(timeout_rows[:50]),
        "error_problems": _problem_rows(error_rows[:50]),
    }
    return overview


def _profile_row(row: RunRow) -> dict[str, Any]:
    serialized = row_to_json(row)
    return {
        "problem_path": serialized["path"],
        "problem": serialized["problem"],
        "status": serialized["status"],
        "raw_status": serialized["szs_status"],
        "outcome": serialized["outcome"],
        "elapsed_seconds": serialized["elapsed_seconds"],
        "steps": serialized["steps"],
        "strategy_count": serialized["strategy_count"],
        "winning_strategy_index": serialized["winning_strategy_index"],
        **(
            {"error": serialized["error_message"]}
            if serialized.get("error_message")
            else {}
        ),
        **(
            {"error_type": serialized["error_type"]}
            if serialized.get("error_type")
            else {}
        ),
    }


def _profile_functions(
    stats: pstats.Stats,
    limit_functions: int | None,
) -> list[dict[str, object]]:
    functions: list[dict[str, object]] = []
    stats_data = _stats_data(stats)
    function_list = _stats_function_list(stats, stats_data)
    if limit_functions is not None:
        function_list = function_list[:limit_functions]
    for rank, func in enumerate(function_list, start=1):
        primitive_calls, total_calls, total_seconds, cumulative_seconds, _callers = (
            stats_data[func]
        )
        filename, line_number, function_name = func
        functions.append(
            {
                "rank": rank,
                "function": function_name,
                "file": filename,
                "line": line_number,
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "total_seconds": total_seconds,
                "cumulative_seconds": cumulative_seconds,
            }
        )
    return functions


def _profile_callers(stats: pstats.Stats) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    stats_data = _stats_data(stats)
    function_order = {
        func: index
        for index, func in enumerate(_stats_function_list(stats, stats_data), start=1)
    }
    for callee, stat in stats_data.items():
        _primitive_calls, _total_calls, _total_seconds, _cumulative_seconds, callers = (
            stat
        )
        callee_file, callee_line, callee_name = callee
        for caller, caller_stats in callers.items():
            caller_file, caller_line, caller_name = caller
            primitive_calls = total_calls = total_seconds = cumulative_seconds = None
            if isinstance(caller_stats, tuple):
                primitive_calls, total_calls, total_seconds, cumulative_seconds = (
                    caller_stats[:4]
                )
            elif isinstance(caller_stats, int):
                total_calls = caller_stats
            rows.append(
                {
                    "callee_rank": function_order.get(callee),
                    "caller_rank": function_order.get(caller),
                    "caller_function": caller_name,
                    "caller_file": caller_file,
                    "caller_line": caller_line,
                    "callee_function": callee_name,
                    "callee_file": callee_file,
                    "callee_line": callee_line,
                    "primitive_calls": primitive_calls,
                    "total_calls": total_calls,
                    "total_seconds": total_seconds,
                    "cumulative_seconds": cumulative_seconds,
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            -float(row["cumulative_seconds"] or 0),
            -float(row["total_seconds"] or 0),
            str(row["callee_function"]),
        ),
    )


def _stats_data(stats: pstats.Stats) -> dict[Any, Any]:
    return getattr(stats, "stats")


def _stats_function_list(
    stats: pstats.Stats,
    stats_data: dict[Any, Any],
) -> list[Any]:
    return list(getattr(stats, "fcn_list", None) or sorted(stats_data))


def _numbers(rows: Sequence[dict[str, Any]], key: str) -> list[float]:
    return [
        float(value)
        for row in rows
        if isinstance((value := row.get(key)), int | float)
    ]


def _profile_quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p90": None, "max": None}
    sorted_values = sorted(values)
    return {
        "p50": _quantile(sorted_values, 0.50),
        "p90": _quantile(sorted_values, 0.90),
        "max": sorted_values[-1],
    }


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _problem_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "problem",
        "problem_path",
        "status",
        "raw_status",
        "elapsed_seconds",
        "steps",
        "error",
    )
    return [{key: row.get(key) for key in fields if key in row} for row in rows]


def _write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _number_or_zero(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


__all__ = [
    "ProfileConfig",
    "build_profile_overview",
    "profile_run_rows",
    "summarize_profile",
]
