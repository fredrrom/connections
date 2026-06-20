from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from lark import UnexpectedInput
from lark.exceptions import UnexpectedToken

from connections.syntax.formula import And, Formula, Impl
from connections.parsing.tptp.grammar import PARSER
from connections.parsing.tptp.transformer import (
    StmtCNF,
    StmtFOF,
    StmtFormula,
    StmtInclude,
    StmtQMF,
    TptpFile,
    TptpToIRTransformer,
)

E_PARSE = "E_PARSE"
E_NON_FOF_TOPLEVEL = "E_NON_FOF_TOPLEVEL"
E_NON_FOF_INCLUDED = "E_NON_FOF_INCLUDED"
E_INCLUDE_CYCLE = "E_INCLUDE_CYCLE"
E_INCLUDE_NOT_FOUND = "E_INCLUDE_NOT_FOUND"


class TPTPParseError(ValueError):
    def __init__(self, code: str, message: str, line: int, column: int):
        super().__init__(f"[{code}] {message} (line {line}, column {column})")
        self.code = code
        self.line = line
        self.column = column


@dataclass(frozen=True)
class IncludeEdge:
    parent: str
    child: str


@dataclass(frozen=True)
class ParsedTPTPDocument:
    path: str
    statements: list[StmtFormula]
    includes: list[StmtInclude]
    include_edges: list[IncludeEdge]
    axiom_formula: Formula | None = None
    conjecture_formula: Formula | None = None
    problem_formula: Formula | None = None


_UNSUPPORTED_ANNOTATED_KINDS = frozenset({"tff", "thf", "tcf", "tpi"})


def _parse(text: str) -> TptpFile:
    tree = PARSER.parse(text)
    transformer = TptpToIRTransformer()
    return transformer.transform(tree)


def parse_tptp(text: str, non_fof_error_code: str = E_NON_FOF_TOPLEVEL) -> TptpFile:
    try:
        return _parse(text)
    except UnexpectedToken as err:
        token_value = str(err.token.value)
        if token_value in _UNSUPPORTED_ANNOTATED_KINDS:
            raise TPTPParseError(
                non_fof_error_code,
                f"Unsupported annotated formula '{token_value}'",
                err.line,
                err.column,
            ) from err
        raise TPTPParseError(
            E_PARSE, "Invalid TPTP syntax", err.line, err.column
        ) from err
    except UnexpectedInput as err:
        raise TPTPParseError(
            E_PARSE, "Invalid TPTP syntax", err.line, err.column
        ) from err


def _resolve_include(
    current_path: Path,
    include_name: str,
    *,
    source_roots: tuple[Path, ...],
) -> Path:
    include_path = Path(include_name)
    candidates: list[Path] = []

    if include_path.is_absolute():
        candidates.append(include_path)
    else:
        candidates.append(current_path.parent / include_path)
        for root in source_roots:
            candidates.append(root / include_path)
            parts = include_path.parts
            if (
                parts
                and parts[0].casefold() == root.name.casefold()
                and len(parts) > 1
            ):
                candidates.append(root.joinpath(*parts[1:]))

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved

    tried = ", ".join(str(candidate.resolve()) for candidate in candidates)
    raise TPTPParseError(
        E_INCLUDE_NOT_FOUND,
        f"Could not resolve include '{include_name}' from '{current_path}'. Tried: {tried}",
        1,
        1,
    )


def parse_tptp_file(
    path: str | Path,
    *,
    source_roots: Iterable[str | Path] | None = None,
) -> ParsedTPTPDocument:
    start_path = Path(path).resolve()
    resolved_source_roots = tuple(Path(root).resolve() for root in source_roots or ())

    def walk(
        current_path: Path,
        names_filter: tuple[str, ...] | None,
        stack: tuple[Path, ...],
    ):
        if current_path in stack:
            raise TPTPParseError(
                E_INCLUDE_CYCLE,
                f"Cyclic include detected for '{current_path}'",
                1,
                1,
            )

        code = E_NON_FOF_TOPLEVEL if not stack else E_NON_FOF_INCLUDED
        entries = parse_tptp(
            _read_tptp_text(current_path),
            non_fof_error_code=code,
        )

        formula_entries: list[StmtFormula] = []
        include_entries: list[StmtInclude] = []
        include_edges: list[IncludeEdge] = []
        axiom_formulas: list[Formula] = []
        conjecture_formula: Formula | None = None

        for entry in entries.items:
            if isinstance(entry, (StmtFOF, StmtCNF, StmtQMF)):
                if names_filter is None or entry.name in names_filter:
                    formula_entries.append(entry)
                    if entry.role == "conjecture":
                        if conjecture_formula is None:
                            conjecture_formula = entry.formula
                    else:
                        axiom_formulas.append(entry.formula)
            elif isinstance(entry, StmtInclude):
                include_entries.append(entry)
                child_path = _resolve_include(
                    current_path,
                    entry.file_name,
                    source_roots=resolved_source_roots,
                )
                include_edges.append(
                    IncludeEdge(parent=str(current_path), child=str(child_path))
                )

                child_names = None
                if entry.selection is not None:
                    selection = entry.selection
                    child_names = None if selection == "*" else tuple(selection)

                child_doc = walk(
                    child_path, child_names, stack + (current_path,)
                )
                formula_entries.extend(child_doc.statements)
                include_entries.extend(child_doc.includes)
                include_edges.extend(child_doc.include_edges)
                if child_doc.problem_formula is not None:
                    axiom_formulas.append(child_doc.problem_formula)

        axiom_formula = _combine_with_conjunction(axiom_formulas)
        problem_formula = _problem_formula(axiom_formula, conjecture_formula)
        return ParsedTPTPDocument(
            path=str(current_path),
            statements=formula_entries,
            includes=include_entries,
            include_edges=include_edges,
            axiom_formula=axiom_formula,
            conjecture_formula=conjecture_formula,
            problem_formula=problem_formula,
        )

    return walk(start_path, None, tuple())


def _read_tptp_text(path: Path) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _combine_with_conjunction(formulas: list[Formula]) -> Formula | None:
    if not formulas:
        return None
    result = formulas[-1]
    for formula in reversed(formulas[:-1]):
        result = And(formula, result)
    return result


def _problem_formula(
    axiom_formula: Formula | None,
    conjecture_formula: Formula | None,
) -> Formula | None:
    if conjecture_formula is None:
        return axiom_formula
    if axiom_formula is None:
        return conjecture_formula
    return Impl(axiom_formula, conjecture_formula)
