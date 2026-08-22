from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any



_PARITY = Path(__file__).resolve().parent


def _module(name: str) -> str:
    return f"pycop.parity.{name}"


VALIDATION_COMMANDS: tuple[tuple[str, str], ...] = (
    ("prefix", _module("run_prefix_parity")),
    ("prefix_equation", _module("run_prefix_equation_parity")),
    (
        "free_variable_admissibility",
        _module("run_free_variable_admissibility_parity"),
    ),
    ("matrix", _module("run_matrix_parity")),
    ("status_check", _module("run_status_check")),
    ("trace", _module("run_trace_parity")),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the connections validation diagnostics as one release gate."
    )
    parser.add_argument("--swipl", default="swipl")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-case timeout passed to status checking, trace parity, and matrix parity.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_names",
        default=[],
        help=(
            "Restrict case names for commands that support --case. May be "
            "repeated."
        ),
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=tuple(name for name, _path in VALIDATION_COMMANDS),
        default=[],
        help="Run only a named validation command. May be repeated.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        choices=tuple(name for name, _path in VALIDATION_COMMANDS),
        default=[],
        help="Skip a named validation command. May be repeated.",
    )
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write one JSON summary row per command instead of a text report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows: list[dict[str, Any]] = []
    for name, module in _selected_commands(args.only, args.skip):
        row = _run_command(
            name,
            module,
            swipl=args.swipl,
            timeout_seconds=args.timeout,
            case_names=args.case_names,
        )
        rows.append(row)
        if args.json:
            print(json.dumps(row, sort_keys=True))
        else:
            status = "ok" if row["passed"] else "failed"
            print(
                f"{status} {name}: exit={row['exit_code']} rows={row['rows']} "
                f"failures={row['failures']}"
            )
        if args.fail_fast and not row["passed"]:
            break

    passed = all(row["passed"] is True for row in rows)
    if not args.json:
        print(
            f"summary: commands={len(rows)} "
            f"passed={sum(row['passed'] is True for row in rows)} "
            f"failed={sum(row['passed'] is not True for row in rows)}"
        )
    return 0 if passed else 1


def _selected_commands(
    only: list[str],
    skip: list[str],
) -> tuple[tuple[str, str], ...]:
    only_set = set(only)
    skip_set = set(skip)
    return tuple(
        (name, module)
        for name, module in VALIDATION_COMMANDS
        if (not only_set or name in only_set) and name not in skip_set
    )


def _run_command(
    name: str,
    module: str,
    *,
    swipl: str,
    timeout_seconds: float,
    case_names: list[str],
) -> dict[str, Any]:
    command = [sys.executable, "-m", module, "--json"]
    if name in {
        "prefix",
        "prefix_equation",
        "free_variable_admissibility",
        "matrix",
        "status_check",
        "trace",
    }:
        command.extend(["--swipl", swipl])
    if name in {"matrix", "status_check", "trace"}:
        command.extend(["--timeout", str(timeout_seconds)])
    if name in {"matrix", "status_check", "trace"}:
        for case_name in case_names:
            command.extend(["--case", case_name])

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    rows = _json_lines(completed.stdout)
    failures = _failure_count(name, rows)
    if completed.returncode != 0 and failures == 0:
        failures = 1
    return {
        "schema": "connections.parity_command_summary.v1",
        "name": name,
        "command": command,
        "exit_code": completed.returncode,
        "passed": completed.returncode == 0,
        "rows": len(rows),
        "failures": failures,
        "stdout": completed.stdout if completed.returncode != 0 else "",
        "stderr": completed.stderr,
    }


def _json_lines(output: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _failure_count(name: str, rows: list[dict[str, Any]]) -> int:
    if name == "prefix":
        return sum(
            row.get("oracle_expected_match") is not True
            or row.get("native_reference_match") is False
            for row in rows
        )
    if name == "prefix_equation":
        return sum(
            row.get("oracle_expected_match") is not True
            or row.get("native_reference_match") is False
            for row in rows
        )
    if name == "free_variable_admissibility":
        return sum(
            row.get("oracle_expected_match") is not True
            or row.get("native_reference_match") is False
            for row in rows
        )
    if name == "matrix":
        return sum(row.get("matrix_match") is False for row in rows)
    if name == "status_check":
        return sum(_status_check_failed(row) for row in rows)
    if name == "trace":
        return sum(row.get("trace_match") is not True for row in rows)
    return 0


def _status_check_failed(row: dict[str, Any]) -> bool:
    if row.get("native_status") == "Error":
        return True
    if row.get("expected_status") is not None:
        return row.get("native_expected_match") is not True
    if row.get("expected_status_label") is not None:
        return False
    return row.get("status_match") is not True


__all__ = ["VALIDATION_COMMANDS", "build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
