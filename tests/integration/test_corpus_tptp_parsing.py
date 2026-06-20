from pathlib import Path

import pytest

from connections.syntax.formula import And, Eq, Exists, Forall, Impl, Not
from connections.parsing.tptp.parser import (
    E_NON_FOF_TOPLEVEL,
    TPTPParseError,
    parse_tptp,
    parse_tptp_file,
)
from connections.parsing.tptp.transformer import StmtFOF, StmtInclude, TptpFile


def _formula_contains(formula, target_types):
    if isinstance(formula, target_types):
        return True
    if isinstance(formula, (Not,)):
        return _formula_contains(formula.formula, target_types)
    if isinstance(formula, (And, Impl)):
        return _formula_contains(formula.left, target_types) or _formula_contains(
            formula.right, target_types
        )
    if isinstance(formula, (Forall, Exists)):
        return _formula_contains(formula.body, target_types)
    return False


@pytest.mark.external_tptp_corpus
def test_syn_corpus_parses_with_strict_expected_outcomes(tptp_root: Path):
    syn_dir = tptp_root / "Problems" / "SYN"
    files = sorted(syn_dir.glob("*.p"))
    assert files, f"No SYN .p files found in {syn_dir}"

    parsed = 0
    non_fof = 0
    unexpected: list[str] = []

    for file in files:
        try:
            parse_tptp(file.read_text())
            parsed += 1
        except TPTPParseError as err:
            if err.code == E_NON_FOF_TOPLEVEL:
                non_fof += 1
            else:
                unexpected.append(f"{file.name}: {err.code} - {err}")

    assert parsed > 0
    assert non_fof > 0
    assert not unexpected, "\n".join(unexpected)


@pytest.mark.external_tptp_corpus
def test_select_syn_fof_files_have_expected_structure(tptp_root: Path):
    syn_dir = tptp_root / "Problems" / "SYN"
    files = sorted(syn_dir.glob("*.p"))

    parsed_docs: list[tuple[Path, TptpFile]] = []
    for file in files:
        try:
            doc = parse_tptp(file.read_text())
        except TPTPParseError as err:
            if err.code == E_NON_FOF_TOPLEVEL:
                continue
            raise
        parsed_docs.append((file, doc))

    assert parsed_docs

    has_include = next(
        (
            item
            for item in parsed_docs
            if any(isinstance(x, StmtInclude) for x in item[1].items)
        ),
        None,
    )
    has_eq = next(
        (
            item
            for item in parsed_docs
            if any(
                isinstance(x, StmtFOF) and _formula_contains(x.formula, (Eq,))
                for x in item[1].items
            )
        ),
        None,
    )
    has_quant = next(
        (
            item
            for item in parsed_docs
            if any(
                isinstance(x, StmtFOF)
                and _formula_contains(x.formula, (Forall, Exists))
                for x in item[1].items
            )
        ),
        None,
    )
    has_annotations = next(
        (
            item
            for item in parsed_docs
            if any(
                isinstance(x, StmtFOF) and x.annotations is not None
                for x in item[1].items
            )
        ),
        None,
    )

    assert has_include is not None
    assert has_eq is not None
    assert has_quant is not None
    assert has_annotations is not None

    include_file = has_include[0]
    doc_with_includes = parse_tptp_file(include_file, source_roots=(tptp_root,))
    assert len(doc_with_includes.includes) > 0
    assert len(doc_with_includes.include_edges) > 0
