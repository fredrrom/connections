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

from connections.constraints.prefix import (
    PrefixEquation,
    prefix_equations_satisfiable,
)
from tools.parity.prefix_cases import (
    DEFAULT_PREFIX_EQUATION_CASES,
    PrefixEquationCase,
)
from tools.parity.prefix_oracle import run_prefix_equation_case
from tools.parity.prefix_syntax import parse_prefix


def native_prefix_equation_case(case: PrefixEquationCase) -> bool:
    variables = {}
    equations = tuple(
        PrefixEquation(
            parse_prefix(left, variables=variables),
            parse_prefix(right, variables=variables),
        )
        for left, right in case.equations
    )
    return prefix_equations_satisfiable(
        equations,
        logic=case.logic,
        domain=case.domain,
    )


def prefix_equation_parity_row(
    case: PrefixEquationCase,
    *,
    prolog_file: str | Path | None = None,
    swipl: str = "swipl",
) -> dict[str, Any]:
    reference = run_prefix_equation_case(case, prolog_file=prolog_file, swipl=swipl)
    try:
        native = native_prefix_equation_case(case)
    except NotImplementedError:
        native = None
    return {
        "schema": "connections.prefix_equation_parity_row.v1",
        "name": case.name,
        "logic": case.logic,
        "domain": case.domain,
        "equations": case.equations,
        "expected": case.expected,
        "reference": reference,
        "native": native,
        "oracle_expected_match": reference == case.expected,
        "native_supported": native is not None,
        "native_reference_match": None if native is None else native == reference,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare native prefix-equation set satisfiability with the Prolog "
            "oracle."
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
        prefix_equation_parity_row(
            case,
            prolog_file=args.prolog_file,
            swipl=args.swipl,
        )
        for case in DEFAULT_PREFIX_EQUATION_CASES
    ]
    if args.json:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    else:
        for row in rows:
            if row["native_supported"]:
                status = "ok" if row["native_reference_match"] else "mismatch"
                detail = f"reference={row['reference']} native={row['native']}"
            else:
                status = "unsupported"
                detail = f"reference={row['reference']}"
            print(f"{status} {row['name']}: {detail}")
    failed = [
        row
        for row in rows
        if row["oracle_expected_match"] is not True
        or row["native_reference_match"] is False
    ]
    return 1 if failed else 0


__all__ = [
    "build_parser",
    "main",
    "native_prefix_equation_case",
    "prefix_equation_parity_row",
]


if __name__ == "__main__":
    raise SystemExit(main())
