from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Literal, Sequence

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.clausification import matrix_from_file
from connections.syntax.formula import Function, Prefix, Term, Variable
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Clause, Literal as MatrixLiteral
from provers.pycop.settings_codec import LeancopSettingsCodec
from connections.runs import select_problem_paths
from tools.parity.run_status_check import ReferenceProver

ReferenceSupport = Literal["supported", "translator_limit"]
_GENERATED_ID_RE = re.compile(r"\b(p_defini|c_skolem|f_skolem)\((\d+)")


@dataclass(frozen=True, slots=True)
class MatrixParityCase:
    name: str
    source: str
    reference: ReferenceProver | None
    logic: Logic
    domain: Domain = "constant"
    settings: tuple[str, ...] = ()
    reference_support: ReferenceSupport = "supported"


DEFAULT_MATRIX_CASES: tuple[MatrixParityCase, ...] = (
    MatrixParityCase(
        name="classical_tautology_matrix",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="leancop21",
        logic="classical",
        settings=("cut", "comp(7)"),
    ),
    MatrixParityCase(
        name="classical_open_atom_matrix",
        source="fof(c,conjecture,p).\n",
        reference="leancop21",
        logic="classical",
        settings=("cut", "comp(7)"),
    ),
    MatrixParityCase(
        name="classical_cnf_native_matrix",
        source="cnf(c1,axiom,p).\ncnf(c2,negated_conjecture,~p).\n",
        reference=None,
        logic="classical",
        settings=("cut", "comp(7)"),
        reference_support="translator_limit",
    ),
    MatrixParityCase(
        name="intuitionistic_tautology_matrix",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="ileancop12",
        logic="intuitionistic",
        settings=("def", "scut", "cut", "comp(7)"),
    ),
    MatrixParityCase(
        name="modal_d_box_implies_diamond_matrix",
        source="qmf(c,conjecture,(#box:p => #dia:p)).\n",
        reference="mleancop13",
        logic="D",
        domain="constant",
        settings=("scut", "cut", "comp(7)"),
    ),
)


def matrix_parity_row(
    case: MatrixParityCase,
    *,
    problem_path: Path,
    swipl: str = "swipl",
    timeout_seconds: float = 10.0,
    source_file_dirs: Sequence[str | Path] = (),
    include_matrices: bool = True,
) -> dict[str, Any]:
    native = native_matrix_dump(
        case,
        problem_path=problem_path,
        source_file_dirs=source_file_dirs,
    )
    if case.reference_support == "translator_limit" or case.reference is None:
        row = {
            "schema": "connections.matrix_parity_row.v1",
            "name": case.name,
            "reference": case.reference,
            "logic": case.logic,
            "domain": case.domain,
            "settings": list(case.settings),
            "source_file_dirs": [
                str(Path(path).resolve()) for path in source_file_dirs
            ],
            "reference_support": case.reference_support,
            "native_clause_count": native["clause_count"],
            "reference_clause_count": None,
            "native_literal_count": native["literal_count"],
            "reference_literal_count": None,
            "matrix_order_match": None,
            "matrix_multiset_match": None,
            "matrix_match": None,
            "divergence": "translator_limit",
        }
        return _with_optional_matrices(row, native, None, include_matrices)

    reference = reference_matrix_dump(
        case,
        problem_path=problem_path,
        swipl=swipl,
        timeout_seconds=timeout_seconds,
        source_file_dirs=source_file_dirs,
    )
    order_match = native["normalized_matrix"] == reference["normalized_matrix"]
    multiset_match = Counter(native["normalized_clauses"]) == Counter(
        reference["normalized_clauses"]
    )
    native_only, reference_only = _clause_diff_examples(
        native,
        reference,
        key="normalized_clauses",
    )
    row = {
        "schema": "connections.matrix_parity_row.v1",
        "name": case.name,
        "reference": case.reference,
        "logic": case.logic,
        "domain": case.domain,
        "settings": list(case.settings),
        "source_file_dirs": [str(Path(path).resolve()) for path in source_file_dirs],
        "reference_support": case.reference_support,
        "native_clause_count": native["clause_count"],
        "reference_clause_count": reference["clause_count"],
        "native_literal_count": native["literal_count"],
        "reference_literal_count": reference["literal_count"],
        "matrix_order_match": order_match,
        "matrix_multiset_match": multiset_match,
        "matrix_match": multiset_match,
        "raw_matrix_order_match": native["matrix"] == reference["matrix"],
        "raw_matrix_multiset_match": Counter(native["clauses"])
        == Counter(reference["clauses"]),
        "divergence": None if multiset_match else _matrix_divergence(native, reference),
        "native_only_clause_examples": native_only,
        "reference_only_clause_examples": reference_only,
    }
    return _with_optional_matrices(row, native, reference, include_matrices)


def native_matrix_dump(
    case: MatrixParityCase,
    *,
    problem_path: Path,
    source_file_dirs: Sequence[str | Path] = (),
) -> dict[str, Any]:
    strategy = LeancopSettingsCodec.from_tokens(list(case.settings))
    matrix_options = strategy.matrix
    matrix = matrix_from_file(
        problem_path,
        translation=matrix_options.translation,
        reorder=matrix_options.reorder,
        start_clauses=matrix_options.start_clauses,
        logic=case.logic,
        domain=case.domain,
        source_file_dirs=source_file_dirs,
    )
    formatter = _NativeMatrixFormatter(nonclassical=case.logic != "classical")
    clauses = [formatter.clause(clause) for clause in matrix.clauses]
    normalized_clauses = _normalize_generated_names(clauses)
    return {
        "matrix": "[" + ",".join(clauses) + "]",
        "clauses": clauses,
        "normalized_matrix": "[" + ",".join(normalized_clauses) + "]",
        "normalized_clauses": normalized_clauses,
        "clause_count": len(clauses),
        "literal_count": sum(len(clause) for clause in matrix.clauses),
    }


def reference_matrix_dump(
    case: MatrixParityCase,
    *,
    problem_path: Path,
    swipl: str,
    timeout_seconds: float,
    source_file_dirs: Sequence[str | Path] = (),
) -> dict[str, Any]:
    completed = subprocess.run(
        _reference_command(case, problem_path=problem_path, swipl=swipl),
        check=False,
        capture_output=True,
        env=_reference_env(source_file_dirs),
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{case.reference} failed for {case.name}: {message}")
    return _parse_reference_matrix_output(completed.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare native source-to-Matrix translation with leanCoP-family "
            "reference translators."
        )
    )
    parser.add_argument("--swipl", default="swipl")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-case timeout in seconds for reference matrix translation.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_names",
        default=[],
        help="Run only a named matrix parity case. May be repeated.",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=[],
        help=(
            "Problem file or directory for corpus matrix parity. When supplied, "
            "built-in cases are not used."
        ),
    )
    parser.add_argument("--pattern", default="*.p")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--logic",
        default="classical",
        choices=("classical", "intuitionistic", "D", "T", "S4", "S5"),
        help="Logic for --path corpus parity.",
    )
    parser.add_argument(
        "--domain",
        default="constant",
        choices=("constant", "cumulative", "varying"),
        help="Domain for --path corpus parity.",
    )
    parser.add_argument(
        "--reference",
        default="leancop21",
        choices=("leancop21", "ileancop12", "mleancop13"),
        help="Reference prover for --path corpus parity.",
    )
    parser.add_argument(
        "--settings",
        "--setting",
        action="append",
        dest="settings",
        default=[],
        help="leanCoP setting token for --path corpus parity. May be repeated.",
    )
    parser.add_argument(
        "--source-dir",
        action="append",
        default=[],
        help=(
            "Directory used to resolve included problem source files. The first "
            "entry is also passed to Prolog references as TPTP."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write JSON rows instead of a text report.",
    )
    parser.add_argument(
        "--omit-matrices",
        action="store_true",
        help=(
            "Omit full serialized matrices from JSON rows. Counts and match "
            "metadata are still included."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows: list[dict[str, Any]] = []
    if args.paths:
        for case, problem_path in _path_cases(args):
            row = matrix_parity_row(
                case,
                problem_path=problem_path,
                swipl=args.swipl,
                timeout_seconds=args.timeout,
                source_file_dirs=tuple(args.source_dir),
                include_matrices=not args.omit_matrices,
            )
            rows.append(row)
            if not args.json:
                _print_text_row(case.name, row)
    else:
        cases = _selected_cases(args.case_names)
        with tempfile.TemporaryDirectory(prefix="connections-matrix-parity-") as tmp:
            tmp_path = Path(tmp)
            for case in cases:
                problem_path = tmp_path / f"{case.name}.p"
                problem_path.write_text(case.source, encoding="utf-8")
                row = matrix_parity_row(
                    case,
                    problem_path=problem_path,
                    swipl=args.swipl,
                    timeout_seconds=args.timeout,
                    source_file_dirs=tuple(args.source_dir),
                    include_matrices=not args.omit_matrices,
                )
                rows.append(row)
                if not args.json:
                    _print_text_row(case.name, row)
    if args.json:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    return 0 if all(row["matrix_match"] is not False for row in rows) else 1


def _print_text_row(name: str, row: dict[str, Any]) -> None:
    if row["matrix_match"] is None:
        status = "translator-limit"
    else:
        status = "ok" if row["matrix_match"] else "mismatch"
    print(
        f"{status} {name}: "
        f"native_clauses={row['native_clause_count']} "
        f"reference_clauses={row['reference_clause_count']} "
        f"native_literals={row['native_literal_count']} "
        f"reference_literals={row['reference_literal_count']} "
        f"order={row['matrix_order_match']} "
        f"multiset={row['matrix_multiset_match']} "
        f"divergence={row['divergence']}"
    )
    native_only = row.get("native_only_clause_examples") or []
    reference_only = row.get("reference_only_clause_examples") or []
    for clause in native_only:
        print(f"  native-only: {clause}")
    for clause in reference_only:
        print(f"  reference-only: {clause}")


class _NativeMatrixFormatter:
    def __init__(self, *, nonclassical: bool) -> None:
        self.nonclassical = nonclassical
        self._variables: dict[Variable, int] = {}

    def clause(self, clause: Clause) -> str:
        literals = "[" + ",".join(self.literal(literal) for literal in clause) + "]"
        if not self.nonclassical:
            return literals
        free_variables = "[" + ",".join(self.term(var) for var in clause.free_variables) + "]"
        return f":({free_variables},{literals})"

    def literal(self, literal: MatrixLiteral) -> str:
        atom = self.atom(literal)
        if literal.prefix is None:
            return atom if literal.polarity else f"-({atom})"
        prefix = self.prefix(literal.prefix)
        if literal.polarity:
            return f":({atom},{prefix})"
        return f":(-({atom}),-({prefix}))"

    def atom(self, literal: MatrixLiteral) -> str:
        atom = literal.atom
        if not atom.args:
            return atom.symbol
        return f"{atom.symbol}({','.join(self.term(arg) for arg in atom.args)})"

    def prefix(self, prefix: Prefix) -> str:
        return "[" + ",".join(self.term(part) for part in prefix.parts) + "]"

    def term(self, term: Term) -> str:
        if type(term) is Variable:
            rendered = self._variable(term)
            if term.prefix is None:
                return rendered
            return f":({rendered},{self.term_prefix(term.prefix)})"
        if type(term) is Function:
            rendered = (
                term.symbol
                if not term.args
                else f"{term.symbol}({','.join(self.term(arg) for arg in term.args)})"
            )
            if term.prefix is None:
                return rendered
            return f":({rendered},{self.term_prefix(term.prefix)})"
        raise TypeError(f"unsupported term: {term!r}")

    def term_prefix(self, prefix: Prefix) -> str:
        if not prefix.parts:
            return "pre"
        return "pre(" + ",".join(self.term(part) for part in prefix.parts) + ")"

    def _variable(self, variable: Variable) -> str:
        index = self._variables.get(variable)
        if index is None:
            index = len(self._variables)
            self._variables[variable] = index
        return f"'$VAR'({index})"


def _selected_cases(case_names: list[str]) -> tuple[MatrixParityCase, ...]:
    if not case_names:
        return DEFAULT_MATRIX_CASES
    selected = set(case_names)
    cases = tuple(case for case in DEFAULT_MATRIX_CASES if case.name in selected)
    missing = selected - {case.name for case in cases}
    if missing:
        raise ValueError(f"unknown matrix parity case(s): {sorted(missing)}")
    return cases


def _path_cases(args: argparse.Namespace) -> tuple[tuple[MatrixParityCase, Path], ...]:
    paths = select_problem_paths(
        args.paths,
        pattern=args.pattern,
        recursive=not args.no_recursive,
        limit=args.limit,
    )
    return tuple(
        (
            MatrixParityCase(
                name=path.name,
                source="",
                reference=args.reference,
                logic=args.logic,
                domain=args.domain,
                settings=tuple(args.settings),
            ),
            path,
        )
        for path in paths
    )


def _reference_command(
    case: MatrixParityCase,
    *,
    problem_path: Path,
    swipl: str,
) -> list[str]:
    source = _reference_source(case.reference)
    compat_source = _prolog_atom(_swi_compatibility_source())
    dump_source = _prolog_atom(_matrix_dump_source())
    goal = _reference_goal(case, problem_path=problem_path)
    wrapped_goal = (
        "set_prolog_flag(encoding,iso_latin_1),"
        f"consult({compat_source}),"
        f"consult({dump_source}),"
        f"consult({_prolog_atom(source)}),"
        f"{goal}"
    )
    return [swipl, "-q", "-g", wrapped_goal, "-t", "halt"]


def _reference_goal(case: MatrixParityCase, *, problem_path: Path) -> str:
    settings = _prolog_settings(case.settings)
    problem = _prolog_atom(problem_path)
    if case.reference == "leancop21":
        return (
            "compat_tptp_axiom_path(AxiomPath),"
            f"leancop_tptp2({problem},AxiomPath,[_],Formula,Conjecture),"
            "(Conjecture\\=[]->Problem1=Formula;"
            "matrix_negated(Formula,Problem1)),"
            "leancop_equal(Problem1,Problem2a),"
            "rename_equal(Problem2a,Problem2),"
            f"make_matrix(Problem2,Matrix,{settings}),"
            "dump_matrix(Matrix)"
        )
    if case.reference == "ileancop12":
        return (
            "compat_tptp_axiom_path(AxiomPath),"
            f"leancop_tptp2({problem},AxiomPath,[_],Formula,Conjecture),"
            "(Conjecture\\=[]->Problem1=Formula;"
            "matrix_implies(Formula,false___,Problem1)),"
            "leancop_equal(Problem1,Problem2a),"
            "rename_equal(Problem2a,Problem2),"
            f"make_matrix_intu(Problem2,RawMatrix,{settings}),"
            "compat_reference_matrix(RawMatrix,Matrix),"
            "dump_matrix(Matrix)"
        )
    if case.reference == "mleancop13":
        return (
            "compat_tptp_axiom_path(AxiomPath),"
            f"nanocop_qmltp2({problem},AxiomPath,[_],Formula,Conjecture),"
            "(Conjecture\\=[]->Problem=Formula;"
            "matrix_negated(Formula,Problem)),"
            "rename_equal(Problem,Problem1),"
            f"make_matrix_modal(Problem1,{settings},RawMatrix),"
            "compat_reference_matrix(RawMatrix,Matrix),"
            "dump_matrix(Matrix)"
        )
    raise ValueError(f"unsupported reference prover: {case.reference!r}")


def _parse_reference_matrix_output(output: str) -> dict[str, Any]:
    matrix: str | None = None
    clauses: list[str] = []
    for line in output.splitlines():
        if line.startswith("MATRIX "):
            matrix = line.removeprefix("MATRIX ").strip()
            continue
        if line.startswith("CLAUSE "):
            clauses.append(line.removeprefix("CLAUSE ").strip())
    if matrix is None:
        raise RuntimeError(f"could not parse reference matrix output: {output!r}")
    normalized_clauses = _normalize_generated_names(clauses)
    return {
        "matrix": matrix,
        "clauses": clauses,
        "normalized_matrix": "[" + ",".join(normalized_clauses) + "]",
        "normalized_clauses": normalized_clauses,
        "clause_count": len(clauses),
        "literal_count": sum(_reference_clause_literal_count(clause) for clause in clauses),
    }


def _matrix_divergence(
    native: dict[str, Any],
    reference: dict[str, Any],
) -> str:
    if len(native["clauses"]) != len(reference["clauses"]):
        return "clause_count_mismatch"
    return "matrix_content_mismatch"


def _clause_diff_examples(
    native: dict[str, Any],
    reference: dict[str, Any],
    *,
    key: str = "clauses",
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    native_counter = Counter(native[key])
    reference_counter = Counter(reference[key])
    native_only = list((native_counter - reference_counter).elements())[:limit]
    reference_only = list((reference_counter - native_counter).elements())[:limit]
    return native_only, reference_only


def _normalize_generated_names(clauses: Sequence[str]) -> list[str]:
    clauses = _normalize_conjecture_markers(clauses)
    generated_ids = {
        match.group(2)
        for clause in clauses
        for match in _GENERATED_ID_RE.finditer(clause)
    }
    id_map = {
        generated_id: index
        for index, generated_id in enumerate(
            sorted(generated_ids, key=lambda value: int(value))
        )
    }

    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}('$GEN'({id_map[match.group(2)]})"

    return [_GENERATED_ID_RE.sub(replace, clause) for clause in clauses]


def _normalize_conjecture_markers(clauses: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for clause in clauses:
        marker_normalized = _normalize_conjecture_marker_clause(clause)
        if marker_normalized is not None:
            normalized.append(marker_normalized)
    return normalized


def _normalize_conjecture_marker_clause(clause: str) -> str | None:
    text = clause.strip()
    if text.startswith("[") and text.endswith("]"):
        return _normalize_conjecture_marker_literal_list(text)
    if not text.startswith(":(") or not text.endswith(")"):
        return text

    inner = text[2:-1]
    split = _top_level_comma_index(inner)
    if split is None:
        return text
    free_variables = inner[:split].strip()
    literal_list = inner[split + 1 :].strip()
    normalized_literals = _normalize_conjecture_marker_literal_list(literal_list)
    if normalized_literals is None:
        return None
    return f":({free_variables},{normalized_literals})"


def _normalize_conjecture_marker_literal_list(literal_list: str) -> str | None:
    if literal_list == "[]":
        return literal_list
    literals = _split_top_level_items(literal_list[1:-1])
    filtered = [literal for literal in literals if literal not in {"#", "-(#)"}]
    if not filtered:
        return None
    return "[" + ",".join(filtered) + "]"


def _split_top_level_items(text: str) -> list[str]:
    if not text:
        return []
    items: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(text[start:index].strip())
            start = index + 1
    items.append(text[start:].strip())
    return items


def _with_optional_matrices(
    row: dict[str, Any],
    native: dict[str, Any],
    reference: dict[str, Any] | None,
    include_matrices: bool,
) -> dict[str, Any]:
    if not include_matrices:
        return row
    row["native_matrix"] = native["matrix"]
    row["native_clauses"] = native["clauses"]
    if reference is None:
        row["reference_matrix"] = None
        row["reference_clauses"] = None
    else:
        row["reference_matrix"] = reference["matrix"]
        row["reference_clauses"] = reference["clauses"]
    return row


def _reference_clause_literal_count(clause: str) -> int:
    text = clause.strip()
    if text.startswith(":("):
        inner = text[2:-1]
        split = _top_level_comma_index(inner)
        if split is None:
            return 0
        literal_list = inner[split + 1 :].strip()
    else:
        literal_list = text
    if literal_list == "[]":
        return 0
    depth = 0
    count = 1
    for char in literal_list[1:-1]:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            count += 1
    return count


def _top_level_comma_index(text: str) -> int | None:
    depth = 0
    for index, char in enumerate(text):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            return index
    return None


def _reference_source(reference: ReferenceProver | None) -> Path:
    if reference == "leancop21":
        return _reference_dir(reference) / "leancop_main_trans.pl"
    if reference == "ileancop12":
        return _reference_dir(reference) / "leancop_main_itrans.pl"
    if reference == "mleancop13":
        return _reference_dir(reference) / "leancop_main_mtrans.pl"
    raise ValueError(f"unsupported reference prover: {reference!r}")


def _reference_dir(reference: ReferenceProver) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "tools" / "parity" / "reference_provers" / "prolog" / reference


def _reference_env(source_file_dirs: Sequence[str | Path]) -> dict[str, str] | None:
    if not source_file_dirs:
        return None
    env = os.environ.copy()
    env["TPTP"] = str(Path(source_file_dirs[0]).resolve())
    return env


def _swi_compatibility_source() -> Path:
    return Path(__file__).resolve().parent / "prolog" / "swi_compat.pl"


def _matrix_dump_source() -> Path:
    return Path(__file__).resolve().parent / "prolog" / "matrix_dump.pl"


def _prolog_atom(value: str | Path) -> str:
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _prolog_settings(settings: tuple[str, ...]) -> str:
    return "[" + ",".join(settings) + "]"


__all__ = [
    "DEFAULT_MATRIX_CASES",
    "MatrixParityCase",
    "build_parser",
    "main",
    "matrix_parity_row",
    "native_matrix_dump",
    "reference_matrix_dump",
]


if __name__ == "__main__":
    raise SystemExit(main())
