from __future__ import annotations

import cProfile
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import pstats
from typing import Any

from connections.runs.run_corpus import (
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
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    elapsed_values = _numbers(rows, "elapsed_seconds")
    matrix_values = _numbers(rows, "matrix_seconds")
    search_values = _numbers(rows, "search_seconds")
    inference_values = _numbers(rows, "inference_actions")
    compare_rows = _performance_compare_rows(rows)
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
        "matrix_seconds": _profile_quantiles(matrix_values),
        "search_seconds": _profile_quantiles(search_values),
        "inference_actions": {
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
        "time_breakdown": _time_breakdown(rows),
    }
    if compare_rows:
        overview["reference"] = _reference_overview(compare_rows)
    if baseline is not None:
        overview["baseline"] = baseline
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
        "inference_actions": serialized["inference_actions"],
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


def _performance_compare_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    compare_rows: list[dict[str, Any]] = []
    for row in rows:
        if "reference_status" not in row and "reference_seconds" not in row:
            continue
        compare_rows.append(
            {
                key: row[key]
                for key in (
                    "problem",
                    "problem_path",
                    "status",
                    "raw_status",
                    "pycop_seconds",
                    "reference_prover",
                    "reference_status",
                    "reference_raw_status",
                    "reference_seconds",
                    "status_match",
                    "pycop_speedup_vs_reference",
                    "strategy_count",
                    "reference_strategy_count",
                    "error",
                    "reference_error",
                )
                if key in row
            }
        )
    return compare_rows


def _reference_overview(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    pycop_solved = sum(1 for row in rows if row.get("status") == "Theorem")
    reference_solved = sum(1 for row in rows if row.get("reference_status") == "Theorem")
    status_matches = sum(1 for row in rows if row.get("status_match") is True)
    speedups = _numbers(rows, "pycop_speedup_vs_reference")
    slower_rows = [
        row
        for row in rows
        if isinstance(row.get("pycop_speedup_vs_reference"), int | float)
        and float(row["pycop_speedup_vs_reference"]) < 1
    ]
    return {
        "schema": "connections.runs_profile_reference_overview.v1",
        "rows": len(rows),
        "status_matches": status_matches,
        "status_match_rate": status_matches / len(rows) if rows else None,
        "pycop_solved": pycop_solved,
        "reference_solved": reference_solved,
        "solved_delta": pycop_solved - reference_solved,
        "pycop_speedup_vs_reference": _profile_quantiles(speedups),
        "slowdowns": _problem_rows(
            sorted(
                slower_rows,
                key=lambda row: float(row.get("pycop_speedup_vs_reference") or 0),
            )[:25]
        ),
    }


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
        "pycop_seconds",
        "reference_prover",
        "reference_status",
        "reference_raw_status",
        "reference_seconds",
        "status_match",
        "pycop_speedup_vs_reference",
        "matrix_seconds",
        "search_seconds",
        "inference_actions",
        "error",
        "reference_error",
    )
    return [{key: row.get(key) for key in fields if key in row} for row in rows]


def _time_breakdown(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    stage_keys = {
        "parsing": ("parse_seconds", "parsing_seconds"),
        "clausification_matrix": (
            "matrix_seconds",
            "clausification_seconds",
            "matrix_construction_seconds",
        ),
        "search": ("search_seconds",),
        "tracing": ("trace_seconds", "tracing_seconds"),
        "overhead": ("overhead_seconds",),
    }
    breakdown: dict[str, float] = {}
    for stage, keys in stage_keys.items():
        total = 0.0
        for row in rows:
            for key in keys:
                value = row.get(key)
                if isinstance(value, int | float):
                    total += float(value)
                    break
        if total:
            breakdown[stage] = total
    return breakdown


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
