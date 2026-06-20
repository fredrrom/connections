from __future__ import annotations

import pytest

from connections.clausification import clausify
from connections.clausification.conversion import mat, prefixed_dnf, prefixed_mat
from connections.syntax.formula import (
    And,
    Atom,
    Box,
    Eq,
    Exists,
    Forall,
    Function,
    Impl,
    Not,
    Or,
    Prefixed,
    Prefix,
    Variable,
)
from connections.syntax.matrix import Matrix
from connections.parsing.tptp.parser import parse_tptp_file
from connections.trace_logging import CLAUSIFICATION_TRACE_LOGGER_NAME, TRACE_LEVEL


def test_clausify_formula_returns_matrix():
    matrix = clausify(
        Or(Atom("p"), Atom("q")),
        translation="nodef",
    )
    assert isinstance(matrix, Matrix)
    assert len(matrix.clauses) == 2


def test_clausify_formula_respects_def_mode():
    formula = And(Or(Atom("p"), Atom("q")), Or(Atom("r"), Atom("s")))
    nodef_matrix = clausify(
        formula,
        translation="nodef",
    )
    def_matrix = clausify(
        formula,
        translation="def",
    )

    assert not any(
        literal.atom.symbol.startswith("p_defini")
        for clause in nodef_matrix.clauses
        for literal in clause.literals
    )
    assert any(
        literal.atom.symbol.startswith("p_defini")
        for clause in def_matrix.clauses
        for literal in clause.literals
    )


def test_clausify_default_translation_handles_left_deep_antecedent():
    antecedent = Atom("p0")
    for index in range(1, 560):
        antecedent = And(antecedent, Atom(f"p{index}"))

    matrix = clausify(
        Impl(antecedent, Atom("goal")),
    )

    assert len(matrix.clauses) == 561


def test_mat_handles_deep_disjunction_without_recursion_error():
    formula = Atom("p0")
    for index in range(1, 1200):
        formula = Or(formula, Atom(f"p{index}"))

    clauses = mat(formula)

    assert len(clauses) == 1200


def test_prefixed_dnf_handles_deep_disjunction_without_recursion_error():
    expr = Prefixed(Atom("p0"), Prefix(()))
    for index in range(1, 1200):
        expr = Or(expr, Prefixed(Atom(f"p{index}"), Prefix(())))

    dnf_expr = prefixed_dnf(expr)
    clauses = prefixed_mat(dnf_expr)

    assert len(clauses) == 1200


def test_prefixed_compound_pushes_prefix_to_literals() -> None:
    prefix = Prefix((Function("w"),))
    expr = Prefixed(Or(Atom("p"), Not(Atom("q"))), prefix)

    clauses = prefixed_mat(prefixed_dnf(expr))

    assert len(clauses) == 2
    assert {clause[0].atom.symbol for clause in clauses} == {"p", "q"}
    assert all(clause[0].prefix == prefix for clause in clauses)


def test_mat_handles_deep_conjunction_without_recursion_error():
    formula = Atom("p0")
    for index in range(1, 200):
        formula = And(formula, Atom(f"p{index}"))

    clauses = mat(formula)

    assert len(clauses) == 1
    assert len(clauses[0]) == 200


def test_clausify_equality_predicate_substitution_keeps_equalities_in_clause():
    a = Function("a")
    b = Function("b")
    matrix = clausify(
        Impl(Eq(a, a), Atom("p", (a, b))),
    )

    predicate_substitution_clauses = [
        clause
        for clause in matrix.clauses
        if sum(literal.atom.symbol == "p" for literal in clause.literals) == 2
        and sum(literal.atom.symbol == "equal___" for literal in clause.literals) == 2
    ]

    assert predicate_substitution_clauses
    for clause in predicate_substitution_clauses:
        p_literals = [
            literal for literal in clause.literals if literal.atom.symbol == "p"
        ]
        equality_literals = [
            literal for literal in clause.literals if literal.atom.symbol == "equal___"
        ]
        assert {literal.polarity for literal in p_literals} == {True, False}
        assert all(literal.polarity for literal in equality_literals)


def test_clausify_classical_rejects_modal_formula():
    with pytest.raises(NotImplementedError, match="modal formulas"):
        clausify(Box(Atom("p")))


def test_clausify_modal_formula_adds_literal_prefix():
    matrix = clausify(Box(Atom("p")), logic="D", translation="nodef")

    assert len(matrix.clauses) == 1
    literal = matrix.clauses[0].literals[0]
    assert literal.atom.symbol == "p"
    assert literal.prefix is not None
    assert str(literal.prefix.parts[0]).startswith("c_skolem")


def test_clausify_intuitionistic_implication_adds_prefixes():
    matrix = clausify(
        Impl(Atom("p"), Atom("q")),
        logic="intuitionistic",
        translation="nodef",
    )

    literals = [clause.literals[0] for clause in matrix.clauses]

    assert [(literal.atom.symbol, literal.polarity) for literal in literals] == [
        ("p", False),
        ("q", True),
    ]
    assert literals[0].prefix == literals[1].prefix
    assert literals[0].prefix is not None
    assert len(literals[0].prefix.parts) == 1


def test_clausify_intuitionistic_forall_not_adds_source_negation_prefix():
    variable = Variable("X")

    matrix = clausify(
        Forall(variable, Not(Atom("p", (variable,)))),
        logic="intuitionistic",
        translation="nodef",
    )

    literal = matrix.clauses[0].literals[0]

    assert literal.atom.symbol == "p"
    assert literal.polarity is False
    assert literal.prefix is not None
    assert len(literal.prefix.parts) == 2
    skolem = literal.atom.args[0]
    assert isinstance(skolem, Function)
    assert skolem.prefix is not None
    assert len(skolem.prefix.parts) == 1


def test_clausify_intuitionistic_negative_exists_does_not_extend_prefix():
    variable = Variable("X")

    matrix = clausify(
        Impl(Exists(variable, Atom("p", (variable,))), Atom("q")),
        logic="intuitionistic",
        translation="nodef",
    )

    negative = next(
        literal
        for clause in matrix.clauses
        for literal in clause.literals
        if literal.atom.symbol == "p"
    )

    assert negative.polarity is False
    assert negative.prefix is not None
    assert len(negative.prefix.parts) == 1
    skolem = negative.atom.args[0]
    assert isinstance(skolem, Function)
    assert skolem.prefix == negative.prefix


def test_clausify_nonclassical_translation_does_not_synthesize_free_variables():
    variable = Variable("X")

    matrix = clausify(
        Exists(variable, Atom("p", (variable,))),
        logic="D",
        translation="nodef",
    )

    assert len(matrix.clauses) == 1
    assert matrix.clauses[0].free_variables == ()


def test_clausify_collects_prefixed_variables_as_clause_free_variables():
    prefix = Prefix((Function("w"),))
    variable = Variable("X", prefix=prefix)

    matrix = clausify(Atom("p", (variable,)), translation="nodef")

    assert matrix.clauses[0].free_variables == (variable,)


def test_clausify_document_marks_conjecture_clauses_without_marker_literals(tmp_path):
    problem = tmp_path / "problem.p"
    problem.write_text(
        "\n".join(["fof(a1,axiom,p).", "fof(c1,conjecture,q)."]), encoding="utf-8"
    )
    parsed = parse_tptp_file(problem)
    matrix = clausify(
        parsed,
        translation="nodef",
        start_clauses="conjecture",
    )

    assert not any(
        literal.atom.symbol == "#"
        for clause in matrix.clauses
        for literal in clause.literals
    )
    assert matrix.conjecture_clauses
    assert any(
        clause.role == "conjecture"
        and any(literal.atom.symbol == "q" for literal in clause.literals)
        for clause in matrix.clauses
    )


def test_clausify_emits_matrix_construction_trace(tmp_path, caplog):
    problem = tmp_path / "problem.p"
    problem.write_text(
        "\n".join(["fof(a1,axiom,p).", "fof(c1,conjecture,p)."]),
        encoding="utf-8",
    )
    parsed = parse_tptp_file(problem)
    caplog.set_level(TRACE_LEVEL, logger=CLAUSIFICATION_TRACE_LOGGER_NAME)

    matrix = clausify(
        parsed,
        translation="nodef",
        start_clauses="conjecture",
    )

    assert caplog.messages[:3] == [
        "clausification.document.start",
        "clausification.document.roles",
        "clausification.document.combine",
    ]
    assert "clausification.document.marker" not in caplog.messages
    assert caplog.messages[-1] == "clausification.done"
    assert len(matrix.clauses) > 0
