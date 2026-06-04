from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Iterable

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

TIMEOUT = "Timeout"


def summarize_trace_rows(
    rows: Iterable[dict[str, Any]],
    *,
    examples: int = 25,
) -> dict[str, Any]:
    all_rows = list(rows)
    error_rows = [row for row in all_rows if "error" in row]
    supported_rows = [row for row in all_rows if "error" not in row]
    native_timeout_only = [
        row
        for row in supported_rows
        if row.get("native_status") == TIMEOUT
        and row.get("reference_status") != TIMEOUT
    ]
    reference_timeout_only = [
        row
        for row in supported_rows
        if row.get("reference_status") == TIMEOUT
        and row.get("native_status") != TIMEOUT
    ]
    both_timeout = [
        row
        for row in supported_rows
        if row.get("native_status") == TIMEOUT
        and row.get("reference_status") == TIMEOUT
    ]
    status_disagreements = [
        row for row in supported_rows if row.get("status_match") is not True
    ]
    trace_disagreements = [
        row for row in supported_rows if row.get("trace_match") is not True
    ]
    non_timeout_trace_disagreements = [
        row
        for row in trace_disagreements
        if row.get("native_status") != TIMEOUT
        and row.get("reference_status") != TIMEOUT
    ]
    return {
        "schema": "connections.trace_parity_summary.v1",
        "rows": len(all_rows),
        "supported_rows": len(supported_rows),
        "error_rows": len(error_rows),
        "error_types": dict(Counter(_error_label(row) for row in error_rows)),
        "trace_matches": sum(row.get("trace_match") is True for row in supported_rows),
        "trace_disagreements": len(trace_disagreements),
        "non_timeout_trace_disagreements": len(non_timeout_trace_disagreements),
        "status_matches": sum(
            row.get("status_match") is True for row in supported_rows
        ),
        "status_disagreements": len(status_disagreements),
        "native_timeout_only": len(native_timeout_only),
        "reference_timeout_only": len(reference_timeout_only),
        "both_timeout": len(both_timeout),
        "status_pairs": dict(
            Counter(
                f"{row.get('native_status')}|{row.get('reference_status')}"
                for row in supported_rows
            )
        ),
        "examples": {
            "native_timeout_only": _examples(native_timeout_only, examples),
            "reference_timeout_only": _examples(reference_timeout_only, examples),
            "status_disagreements": _examples(status_disagreements, examples),
            "non_timeout_trace_disagreements": _examples(
                non_timeout_trace_disagreements, examples
            ),
            "errors": _examples(error_rows, examples),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize trace parity JSONL rows.")
    parser.add_argument("path", help="Trace parity JSONL artifact")
    parser.add_argument("--examples", type=int, default=25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = _read_jsonl(Path(args.path))
    print(json.dumps(summarize_trace_rows(rows, examples=args.examples), indent=2))
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _error_label(row: dict[str, Any]) -> str:
    message = str(row.get("error", ""))
    return message.splitlines()[0] if message else "error"


def _examples(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "name": row.get("name"),
            "native_status": row.get("native_status"),
            "reference_status": row.get("reference_status"),
            "native_trace_length": row.get("native_trace_length"),
            "reference_trace_length": row.get("reference_trace_length"),
            "first_difference": row.get("first_difference"),
            "error": row.get("error"),
        }
        for row in rows[:limit]
    ]


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["summarize_trace_rows"]
