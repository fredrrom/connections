from pathlib import Path

import pytest

from connections.syntax.formula import (
    And,
    Atom,
    Box,
    Diamond,
    Eq,
    Exists,
    Forall,
    Function,
    Impl,
    Not,
    Or,
)
from connections.parsing.tptp.parser import (
    E_INCLUDE_NOT_FOUND,
    E_NON_FOF_INCLUDED,
    E_NON_FOF_TOPLEVEL,
    TPTPParseError,
    parse_tptp,
    parse_tptp_file,
)
from connections.parsing.tptp.grammar import PARSER
from connections.parsing.tptp.transformer import StmtCNF, StmtFOF, StmtInclude, StmtQMF


def test_grammar_module_parses_minimal_inputs():
    fof_tree = PARSER.parse("fof(a,axiom,p).")
    cnf_tree = PARSER.parse("cnf(a,axiom,(p | ~q)).")
    qmf_tree = PARSER.parse("qmf(a,axiom,#box:p).")
    include_tree = PARSER.parse("include('Axioms/SYN000+0.ax').")

    assert fof_tree.data == "tptp_file"
    assert cnf_tree.data == "tptp_file"
    assert qmf_tree.data == "tptp_file"
    assert include_tree.data == "tptp_file"


def test_errors_module_formats_error_message():
    err = TPTPParseError("E_SAMPLE", "sample", 2, 5)
    assert err.code == "E_SAMPLE"
    assert "(line 2, column 5)" in str(err)


def test_parse_single_fof_statement_to_ir():
    text = "fof(ax1,axiom, ! [X] : (p(X) => q(X)))."
    statements = parse_tptp(text).items

    assert len(statements) == 1
    stmt = statements[0]
    assert isinstance(stmt, StmtFOF)
    assert stmt.name == "ax1"
    assert stmt.role == "axiom"
    assert isinstance(stmt.formula, Forall)
    assert isinstance(stmt.formula.body, Impl)


def test_parse_function_terms_use_string_symbols_not_lark_trees():
    stmt = parse_tptp("fof(a,axiom,p(f(X))).").items[0]
    assert isinstance(stmt, StmtFOF)
    assert isinstance(stmt.formula, Atom)
    assert isinstance(stmt.formula.symbol, str)
    assert stmt.formula.symbol == "p"
    assert len(stmt.formula.args) == 1
    arg = stmt.formula.args[0]
    assert isinstance(arg, Function)
    assert isinstance(arg.symbol, str)
    assert arg.symbol == "f"


def test_parse_defined_numeric_term_uses_string_symbol():
    stmt = parse_tptp("fof(a,axiom,p(42)).").items[0]
    assert isinstance(stmt, StmtFOF)
    assert isinstance(stmt.formula, Atom)
    assert len(stmt.formula.args) == 1
    arg = stmt.formula.args[0]
    assert isinstance(arg, Function)
    assert isinstance(arg.symbol, str)
    assert arg.symbol == "42"


def test_parse_connectives_without_rewrite():
    text = "fof(c,conjecture, ? [X] : ((p(X) <= q(X)) ~& (X != a)))."
    stmt = parse_tptp(text).items[0]

    assert isinstance(stmt, StmtFOF)
    assert stmt.role == "conjecture"
    assert isinstance(stmt.formula, Exists)
    body = stmt.formula.body
    assert isinstance(body, Not)
    assert isinstance(body.formula, And)
    left = body.formula.left
    right = body.formula.right
    assert isinstance(left, Impl)
    assert isinstance(right, Not)
    assert isinstance(right.formula, Eq)


def test_parse_defined_truth_constants_like_leancop_translator():
    true_stmt = parse_tptp("fof(t,axiom,$true).").items[0]
    false_stmt = parse_tptp("fof(f,axiom,$false).").items[0]

    assert isinstance(true_stmt, StmtFOF)
    assert isinstance(true_stmt.formula, Impl)
    assert isinstance(true_stmt.formula.left, Atom)
    assert true_stmt.formula.left.symbol == "true___"
    assert true_stmt.formula.left == true_stmt.formula.right
    assert isinstance(false_stmt, StmtFOF)
    assert isinstance(false_stmt.formula, And)
    assert isinstance(false_stmt.formula.left, Atom)
    assert false_stmt.formula.left.symbol == "false___"
    assert isinstance(false_stmt.formula.right, Not)
    assert false_stmt.formula.right.formula == false_stmt.formula.left


def test_parse_qmf_modal_box_to_ir():
    stmt = parse_tptp("qmf(m1,axiom,#box:p(a)).").items[0]

    assert isinstance(stmt, StmtQMF)
    assert stmt.name == "m1"
    assert stmt.role == "axiom"
    assert isinstance(stmt.formula, Box)
    assert stmt.formula.index is None
    assert isinstance(stmt.formula.body, Atom)
    assert stmt.formula.body.symbol == "p"


def test_parse_cnf_disjunction_to_ir():
    stmt = parse_tptp("cnf(c1,axiom,(p(a) | ~q(X) | X != a)).").items[0]

    assert isinstance(stmt, StmtCNF)
    assert stmt.name == "c1"
    assert stmt.role == "axiom"
    assert isinstance(stmt.formula, Or)
    assert isinstance(stmt.formula.left, Atom)
    assert stmt.formula.left.symbol == "p"
    assert isinstance(stmt.formula.right, Or)
    assert isinstance(stmt.formula.right.left, Not)
    assert isinstance(stmt.formula.right.left.formula, Atom)
    assert isinstance(stmt.formula.right.right, Not)
    assert isinstance(stmt.formula.right.right.formula, Eq)


def test_parse_cnf_equality_literal_to_ir():
    stmt = parse_tptp("cnf(c2,negated_conjecture,(X = a)).").items[0]

    assert isinstance(stmt, StmtCNF)
    assert stmt.role == "negated_conjecture"
    assert isinstance(stmt.formula, Eq)


def test_parse_qmf_indexed_modal_diamond_to_ir():
    stmt = parse_tptp("qmf(m2,conjecture,#dia(w):(? [X] : p(X))).").items[0]

    assert isinstance(stmt, StmtQMF)
    assert stmt.role == "conjecture"
    assert isinstance(stmt.formula, Diamond)
    assert isinstance(stmt.formula.index, Function)
    assert stmt.formula.index.symbol == "w"
    assert isinstance(stmt.formula.body, Exists)


def test_parse_tptp_file_keeps_qmf_formula_entries(tmp_path: Path):
    base = tmp_path / "modal.p"
    base.write_text("qmf(m1,axiom,#box:p).\nqmf(m2,conjecture,#dia:p).\n")

    doc = parse_tptp_file(base)

    assert [stmt.name for stmt in doc.statements] == ["m1", "m2"]
    assert isinstance(doc.statements[0], StmtQMF)
    assert isinstance(doc.axiom_formula, Box)
    assert isinstance(doc.conjecture_formula, Diamond)
    assert isinstance(doc.problem_formula, Impl)


def test_parse_tptp_file_accepts_latin1_comments(tmp_path: Path):
    base = tmp_path / "latin1.p"
    base.write_bytes(b"% author: Andr\xe9\nfof(c,conjecture,p=>p).\n")

    doc = parse_tptp_file(base)

    assert [stmt.name for stmt in doc.statements] == ["c"]


def test_unsupported_annotated_statements_raise_hard_error():
    text = "tff(t1,axiom,$true)."

    with pytest.raises(TPTPParseError) as err:
        parse_tptp(text)

    assert err.value.code == E_NON_FOF_TOPLEVEL
    assert "Unsupported annotated formula 'tff'" in str(err.value)


def test_unsupported_annotated_statement_in_included_file_raises_included_code(
    tmp_path: Path,
):
    base = tmp_path / "base.p"
    inc = tmp_path / "inc.p"

    inc.write_text("tff(i1,axiom,$true).\n")
    base.write_text("include('inc.p').\nfof(main,conjecture,p).\n")

    with pytest.raises(TPTPParseError) as err:
        parse_tptp_file(base)

    assert err.value.code == E_NON_FOF_INCLUDED


def test_parse_include_can_load_cnf_statements(tmp_path: Path):
    base = tmp_path / "base.p"
    inc = tmp_path / "inc.p"

    inc.write_text("cnf(i1,axiom,(p(a) | ~q(a))).\n")
    base.write_text("include('inc.p').\nfof(main,conjecture,p(a)).\n")

    doc = parse_tptp_file(base)

    assert [stmt.name for stmt in doc.statements] == ["i1", "main"]
    assert isinstance(doc.statements[0], StmtCNF)
    assert isinstance(doc.axiom_formula, Or)


def test_parse_include_statement_and_resolve(tmp_path: Path):
    base = tmp_path / "base.p"
    inc = tmp_path / "inc.ax"

    inc.write_text("fof(i1,axiom,p(a)).\nfof(i2,axiom,q(a)).\n")
    base.write_text("include('inc.ax',[i2]).\nfof(main,conjecture, ? [X] : q(X)).\n")
    direct = parse_tptp(base.read_text()).items
    assert isinstance(direct[0], StmtInclude)
    assert direct[0].selection == ("i2",)

    doc = parse_tptp_file(base, source_roots=(tmp_path,))
    assert [stmt.name for stmt in doc.statements] == ["i2", "main"]
    assert len(doc.includes) == 1
    assert doc.includes[0].file_name == "inc.ax"
    assert len(doc.include_edges) == 1


def test_parse_include_preserves_included_file_as_formula_group(tmp_path: Path):
    base = tmp_path / "base.p"
    inc = tmp_path / "inc.ax"

    inc.write_text("fof(i1,axiom,p(a)).\nfof(i2,axiom,q(a)).\n")
    base.write_text("include('inc.ax').\nfof(main,axiom,r(a)).\n")

    doc = parse_tptp_file(base, source_roots=(tmp_path,))

    assert isinstance(doc.axiom_formula, And)
    assert isinstance(doc.axiom_formula.left, And)
    assert isinstance(doc.axiom_formula.right, Atom)
    assert doc.axiom_formula.right.symbol == "r"


def test_tptp_axioms_source_dir_resolves_prefixed_include(tmp_path: Path):
    tptp_root = tmp_path / "TPTP-v-test"
    axioms = tptp_root / "Axioms"
    problems = tptp_root / "Problems" / "SYN"
    axioms.mkdir(parents=True)
    problems.mkdir(parents=True)
    inc = axioms / "SYN000+0.ax"
    base = problems / "SYN000+1.p"

    inc.write_text("fof(i1,axiom,p(a)).\n", encoding="utf-8")
    base.write_text(
        "include('Axioms/SYN000+0.ax').\nfof(main,conjecture,p(a)).\n",
        encoding="utf-8",
    )

    doc = parse_tptp_file(base, source_roots=(axioms,))

    assert [stmt.name for stmt in doc.statements] == ["i1", "main"]
    assert doc.include_edges[0].child == str(inc.resolve())


def test_formula_annotations_are_preserved_as_raw_objects():
    text = "fof(ax1,axiom,p(a),inference(cnf_conversion,[],[axiom1]))."
    statement = parse_tptp(text).items[0]

    assert isinstance(statement, StmtFOF)
    assert statement.annotations is not None


def test_missing_include_raises_include_not_found(tmp_path: Path):
    base = tmp_path / "base.p"
    base.write_text("include('Axioms/DOES_NOT_EXIST.ax').\nfof(main,conjecture,p).\n")

    with pytest.raises(TPTPParseError) as err:
        parse_tptp_file(base, source_roots=(tmp_path,))

    assert err.value.code == E_INCLUDE_NOT_FOUND
