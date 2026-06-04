from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from tools.parity.prefix_cases import (
    DEFAULT_PREFIX_CASES,
    FreeVariableCase,
    PrefixCase,
    PrefixEquationCase,
)

MLEAN_LOGICS = {"d", "t", "s4", "s5", "multi"}
ILEAN_LOGICS = {"intuitionistic", "intu"}
MLEAN_DOMAINS = {"const", "cumul", "vary"}


def run_prefix_case(
    case: PrefixCase,
    *,
    prolog_file: str | Path | None = None,
    swipl: str = "swipl",
) -> bool:
    if case.logic.lower() in ILEAN_LOGICS:
        source = default_ileancop_source() if prolog_file is None else Path(prolog_file)
        goal = _intuitionistic_goal_for_case(case)
    else:
        source = default_mleancop_source() if prolog_file is None else Path(prolog_file)
        goal = _goal_for_case(case)
    return _run_prefix_goal(case.name, goal, source=source, swipl=swipl)


def run_prefix_equation_case(
    case: PrefixEquationCase,
    *,
    prolog_file: str | Path | None = None,
    swipl: str = "swipl",
) -> bool:
    if case.logic.lower() in ILEAN_LOGICS:
        source = default_ileancop_source() if prolog_file is None else Path(prolog_file)
        goal = _intuitionistic_goal_for_equation_case(case)
    else:
        source = default_mleancop_source() if prolog_file is None else Path(prolog_file)
        goal = _goal_for_equation_case(case)
    return _run_prefix_goal(case.name, goal, source=source, swipl=swipl)


def run_free_variable_case(
    case: FreeVariableCase,
    *,
    prolog_file: str | Path | None = None,
    swipl: str = "swipl",
) -> bool:
    if case.logic.lower() in ILEAN_LOGICS:
        source = default_ileancop_source() if prolog_file is None else Path(prolog_file)
        goal = _intuitionistic_goal_for_free_variable_case(case)
    else:
        source = default_mleancop_source() if prolog_file is None else Path(prolog_file)
        goal = _goal_for_free_variable_case(case)
    return _run_prefix_goal(case.name, goal, source=source, swipl=swipl)


def _run_prefix_goal(
    name: str,
    goal: str,
    *,
    source: Path,
    swipl: str,
) -> bool:
    completed = subprocess.run(
        [swipl, "-q", "-s", str(source), "-g", goal, "-t", "halt"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"prefix oracle failed for {name}: {message}")
    output = completed.stdout.strip().splitlines()
    if output == ["success"]:
        return True
    if output == ["failure"]:
        return False
    raise RuntimeError(f"unexpected prefix oracle output for {name}: {output!r}")


def default_mleancop_source() -> Path:
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "tools"
        / "parity"
        / "reference_provers"
        / "prolog"
        / "mleancop13"
        / "mleancop13_swi.pl"
    )
    if not source.exists():
        raise FileNotFoundError(f"mleancop13_swi.pl was not found at {source}")
    return source


def default_ileancop_source() -> Path:
    root = Path(__file__).resolve().parents[2]
    source = (
        root
        / "tools"
        / "parity"
        / "reference_provers"
        / "prolog"
        / "ileancop12"
        / "ileancop12.pl"
    )
    if not source.exists():
        raise FileNotFoundError(f"ileancop12.pl was not found at {source}")
    return source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ask the Prolog mleanCoP prefix-unification oracle."
    )
    parser.add_argument("--prolog-file", metavar="PATH")
    parser.add_argument("--swipl", default="swipl")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write JSON rows instead of a text report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows: list[dict[str, object]] = []
    for case in DEFAULT_PREFIX_CASES:
        actual = run_prefix_case(
            case,
            prolog_file=args.prolog_file,
            swipl=args.swipl,
        )
        row = _row(case, actual=actual)
        rows.append(row)
        if not args.json:
            status = "ok" if row["match"] else "mismatch"
            print(f"{status} {case.name}: expected={case.expected} actual={actual}")
    if args.json:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    return 0 if all(row["match"] is True for row in rows) else 1


def _goal_for_case(case: PrefixCase) -> str:
    logic = _normalize_logic(case.logic)
    domain = _normalize_domain(case.domain)
    return (
        f"abolish(logic/1),assertz(logic({logic})),"
        f"abolish(domain/1),assertz(domain({domain})),"
        f"((prefix_unify([{case.left}={case.right}]))"
        " -> writeln(success) ; writeln(failure))"
    )


def _intuitionistic_goal_for_case(case: PrefixCase) -> str:
    _normalize_intuitionistic_logic(case.logic)
    return (
        f"((prefix_unify([{case.left}={case.right}]))"
        " -> writeln(success) ; writeln(failure))"
    )


def _goal_for_equation_case(case: PrefixEquationCase) -> str:
    logic = _normalize_logic(case.logic)
    domain = _normalize_domain(case.domain)
    equations = ",".join(f"{left}={right}" for left, right in case.equations)
    return (
        f"abolish(logic/1),assertz(logic({logic})),"
        f"abolish(domain/1),assertz(domain({domain})),"
        f"((prefix_unify([{equations}]))"
        " -> writeln(success) ; writeln(failure))"
    )


def _goal_for_free_variable_case(case: FreeVariableCase) -> str:
    logic = _normalize_logic(case.logic)
    domain = _normalize_domain(case.domain)
    conditions = ",".join(
        f"[{_prolog_free_variable_term(variable, resolved, resolved_prefix)},{prefix}]"
        for variable, prefix, resolved, resolved_prefix in case.free_variables
    )
    return (
        f"abolish(logic/1),assertz(logic({logic})),"
        f"abolish(domain/1),assertz(domain({domain})),"
        f"((domain_cond([{conditions}]))"
        " -> writeln(success) ; writeln(failure))"
    )


def _intuitionistic_goal_for_equation_case(case: PrefixEquationCase) -> str:
    _normalize_intuitionistic_logic(case.logic)
    equations = ",".join(f"{left}={right}" for left, right in case.equations)
    return (
        f"((prefix_unify([{equations}]))"
        " -> writeln(success) ; writeln(failure))"
    )


def _intuitionistic_goal_for_free_variable_case(
    case: FreeVariableCase,
) -> str:
    _normalize_intuitionistic_logic(case.logic)
    conditions = ",".join(
        f"[{_prolog_free_variable_term(variable, resolved, resolved_prefix)},{prefix}]"
        for variable, prefix, resolved, resolved_prefix in case.free_variables
    )
    return f"((check_addco([{conditions}])) -> writeln(success) ; writeln(failure))"


def _row(case: PrefixCase, *, actual: bool) -> dict[str, Any]:
    return {
        "schema": "connections.prefix_oracle_row.v1",
        "name": case.name,
        "logic": case.logic,
        "domain": case.domain,
        "left": case.left,
        "right": case.right,
        "expected": case.expected,
        "actual": actual,
        "match": actual == case.expected,
    }


def _normalize_logic(logic: str) -> str:
    normalized = logic.lower()
    if normalized not in MLEAN_LOGICS:
        raise ValueError(f"unsupported mleanCoP logic: {logic!r}")
    return normalized


def _normalize_intuitionistic_logic(logic: str) -> str:
    normalized = logic.lower()
    if normalized not in ILEAN_LOGICS:
        raise ValueError(f"unsupported iLeanCoP logic: {logic!r}")
    return normalized


def _normalize_domain(domain: str) -> str:
    normalized = domain.lower()
    if normalized == "constant":
        normalized = "const"
    if normalized == "cumulative":
        normalized = "cumul"
    if normalized == "varying":
        normalized = "vary"
    if normalized not in MLEAN_DOMAINS:
        raise ValueError(f"unsupported mleanCoP domain: {domain!r}")
    return normalized


def _prolog_free_variable_term(
    variable: str,
    resolved: str | None,
    resolved_prefix: str | None,
) -> str:
    if resolved is None:
        return variable
    if resolved_prefix is None:
        return resolved
    return f"({resolved}^x^{resolved_prefix})"


__all__ = [
    "build_parser",
    "default_ileancop_source",
    "default_mleancop_source",
    "main",
    "run_free_variable_case",
    "run_prefix_case",
    "run_prefix_equation_case",
]


if __name__ == "__main__":
    raise SystemExit(main())
