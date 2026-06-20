from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.constraints.prefix import free_variables_admissible
from connections.syntax.formula import Function, Prefix, Term, Variable
from tools.parity.prefix_cases import (
    DEFAULT_FREE_VARIABLE_CASES,
    FreeVariableCase,
)
from tools.parity.prefix_oracle import run_free_variable_case
from tools.parity.prefix_syntax import parse_prefix, parse_term


def native_free_variable_case(case: FreeVariableCase) -> bool:
    variables: dict[str, Variable] = {}
    free_variables: list[Variable] = []
    resolved_terms: dict[Variable, Term] = {}
    for variable, prefix, resolved, resolved_prefix in case.free_variables:
        free_variable = _variable_with_prefix(
            parse_term(variable, variables=variables),
            parse_prefix(prefix, variables=variables),
        )
        free_variables.append(free_variable)
        if resolved is not None:
            resolved_terms[free_variable] = _term_with_optional_prefix(
                parse_term(resolved, variables=variables),
                None if resolved_prefix is None else parse_prefix(resolved_prefix),
            )
    return free_variables_admissible(
        tuple(free_variables),
        logic=case.logic,
        domain=case.domain,
        resolved_terms=resolved_terms,
    )


def free_variable_parity_row(
    case: FreeVariableCase,
    *,
    prolog_file: str | Path | None = None,
    swipl: str = "swipl",
) -> dict[str, Any]:
    reference = run_free_variable_case(case, prolog_file=prolog_file, swipl=swipl)
    native = native_free_variable_case(case)
    return {
        "schema": "connections.free_variable_admissibility_parity_row.v1",
        "name": case.name,
        "logic": case.logic,
        "domain": case.domain,
        "free_variables": case.free_variables,
        "expected": case.expected,
        "reference": reference,
        "native": native,
        "oracle_expected_match": reference == case.expected,
        "native_reference_match": native == reference,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare native free-variable admissibility with the Prolog oracle."
        )
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
    rows = [
        free_variable_parity_row(
            case,
            prolog_file=args.prolog_file,
            swipl=args.swipl,
        )
        for case in DEFAULT_FREE_VARIABLE_CASES
    ]
    if args.json:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    else:
        for row in rows:
            status = "ok" if row["native_reference_match"] else "mismatch"
            detail = f"reference={row['reference']} native={row['native']}"
            print(f"{status} {row['name']}: {detail}")
    failed = [
        row
        for row in rows
        if row["oracle_expected_match"] is not True
        or row["native_reference_match"] is False
    ]
    return 1 if failed else 0


def _variable_with_prefix(term: Term, prefix: Prefix) -> Variable:
    if type(term) is not Variable:
        raise ValueError(f"free variable must parse as a variable: {term!r}")
    return Variable(term.symbol, prefix=prefix, vid=term.vid)


def _term_with_optional_prefix(term: Term, prefix: Prefix | None) -> Term:
    if prefix is None:
        return term
    if type(term) is Variable:
        return Variable(term.symbol, prefix=prefix, vid=term.vid)
    if type(term) is Function:
        return Function(term.symbol, term.args, prefix=prefix)
    raise TypeError(f"unsupported term: {term!r}")


__all__ = [
    "build_parser",
    "free_variable_parity_row",
    "main",
    "native_free_variable_case",
]


if __name__ == "__main__":
    raise SystemExit(main())
