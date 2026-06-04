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

from connections.constraints.prefix import prefix_unifiable_from_empty
from tools.parity.prefix_cases import DEFAULT_PREFIX_CASES, PrefixCase
from tools.parity.prefix_oracle import run_prefix_case
from tools.parity.prefix_syntax import parse_prefix


def native_prefix_case(case: PrefixCase) -> bool:
    variables = {}
    left = parse_prefix(case.left, variables=variables)
    right = parse_prefix(case.right, variables=variables)
    return prefix_unifiable_from_empty(
        left,
        right,
        logic=case.logic,
        domain=case.domain,
    )


def prefix_parity_row(
    case: PrefixCase,
    *,
    prolog_file: str | Path | None = None,
    swipl: str = "swipl",
) -> dict[str, Any]:
    reference = run_prefix_case(case, prolog_file=prolog_file, swipl=swipl)
    try:
        native = native_prefix_case(case)
    except NotImplementedError:
        native = None
    return {
        "schema": "connections.prefix_parity_row.v1",
        "name": case.name,
        "logic": case.logic,
        "domain": case.domain,
        "left": case.left,
        "right": case.right,
        "expected": case.expected,
        "reference": reference,
        "native": native,
        "oracle_expected_match": reference == case.expected,
        "native_supported": native is not None,
        "native_reference_match": None if native is None else native == reference,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare native prefix unification with the Prolog oracle."
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
        prefix_parity_row(case, prolog_file=args.prolog_file, swipl=args.swipl)
        for case in DEFAULT_PREFIX_CASES
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
    "native_prefix_case",
    "prefix_parity_row",
]


if __name__ == "__main__":
    raise SystemExit(main())
