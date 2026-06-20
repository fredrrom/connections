from __future__ import annotations

import pytest

from connections.clausification import matrix_from_file
from connections.syntax.matrix import Matrix, SignedPredicateSymbol
from connections.parsing.tptp.parser import TPTPParseError
from connections.prover.prover import Problem
from connections.trace_logging import CLAUSIFICATION_TRACE_LOGGER_NAME, TRACE_LEVEL


def _assert_matrix_indices_consistent(matrix: Matrix) -> None:
    expected_graph: dict[SignedPredicateSymbol, list[tuple[int, int]]] = {}
    expected_positive: list[int] = []
    expected_conjecture: list[int] = []

    for clause_idx, clause in enumerate(matrix.clauses):
        if all(lit.polarity for lit in clause.literals):
            expected_positive.append(clause_idx)
        if clause.role == "conjecture":
            expected_conjecture.append(clause_idx)
        for lit_idx, lit in enumerate(clause.literals):
            expected_graph.setdefault(lit.signed_symbol, []).append(
                (clause_idx, lit_idx)
            )

    expected_graph_frozen = {key: tuple(value) for key, value in expected_graph.items()}
    assert matrix.connection_graph == expected_graph_frozen
    assert matrix.positive_clauses == tuple(expected_positive)
    assert matrix.conjecture_clauses == tuple(expected_conjecture)


def test_matrix_from_file_python_initializes_all_indices(tmp_path):
    problem = tmp_path / "indices_python.p"
    problem.write_text("fof(a1,axiom,p).\n", encoding="utf-8")
    matrix = matrix_from_file(
        problem,
        logic="classical",
    )
    _assert_matrix_indices_consistent(matrix)


def test_matrix_from_file_uses_direct_cnf_matrix_construction(tmp_path):
    problem = tmp_path / "cnf_problem.p"
    problem.write_text(
        "\n".join(
            [
                "cnf(c1,axiom,(p(a) | ~q(X))).",
                "cnf(c2,negated_conjecture,(q(a))).",
            ]
        ),
        encoding="utf-8",
    )

    matrix = matrix_from_file(problem, logic="classical")

    _assert_matrix_indices_consistent(matrix)
    assert matrix.source_has_conjecture is False
    assert matrix.conjecture_clauses == (1,)
    assert Problem(matrix=matrix, start_clauses="conjecture").start_clause_ids == (1,)
    assert [
        (clause.role, [str(literal) for literal in clause.literals])
        for clause in matrix.clauses
    ] == [
        ("axiom", ["p(a)", "-q(X)"]),
        ("conjecture", ["q(a)"]),
    ]


def test_matrix_from_file_cnf_maps_equality_literals(tmp_path):
    problem = tmp_path / "cnf_equality.p"
    problem.write_text("cnf(c1,axiom,(X = a | X != b)).\n", encoding="utf-8")

    matrix = matrix_from_file(problem, logic="classical")

    assert [str(literal) for literal in matrix.clauses[0].literals] == [
        "equal___(X,a)",
        "-equal___(X,b)",
    ]


def test_matrix_from_file_rejects_mixed_cnf_and_fof(tmp_path):
    problem = tmp_path / "mixed.p"
    problem.write_text(
        "cnf(c1,axiom,(p)).\nfof(f1,axiom,q).\n",
        encoding="utf-8",
    )

    with pytest.raises(NotImplementedError, match="mixed CNF"):
        matrix_from_file(problem, logic="classical")


def test_matrix_from_file_supports_intuitionistic_fof(tmp_path):
    problem = tmp_path / "intu_problem.p"
    problem.write_text("fof(c1,conjecture,(p => p)).\n", encoding="utf-8")

    matrix = matrix_from_file(
        problem,
        logic="intuitionistic",
        translation="nodef",
    )

    _assert_matrix_indices_consistent(matrix)
    assert matrix.source_has_conjecture is True
    assert any(literal.prefix is not None for clause in matrix for literal in clause)


def test_matrix_from_file_supports_modal_qmf(tmp_path):
    problem = tmp_path / "modal_problem.p"
    problem.write_text("qmf(c1,conjecture,#box:p).\n", encoding="utf-8")

    matrix = matrix_from_file(
        problem,
        logic="D",
        translation="nodef",
    )

    _assert_matrix_indices_consistent(matrix)
    assert matrix.source_has_conjecture is True
    assert any(literal.prefix is not None for clause in matrix for literal in clause)


def test_matrix_from_file_modal_false_conjecture_does_not_emit_false_clause(tmp_path):
    problem = tmp_path / "modal_false_conjecture.p"
    problem.write_text(
        "\n".join(
            [
                "qmf(a1,axiom,p).",
                "qmf(c1,conjecture,$false).",
            ]
        ),
        encoding="utf-8",
    )

    matrix = matrix_from_file(
        problem,
        logic="D",
    )

    symbols = {
        literal.atom.symbol for clause in matrix.clauses for literal in clause.literals
    }
    assert matrix.source_has_conjecture is True
    assert "false___" not in symbols
    assert "$false" not in symbols


def test_matrix_from_file_cnf_conjecture_role_is_not_source_conjecture(tmp_path):
    problem = tmp_path / "cnf_legacy_conjecture.p"
    problem.write_text("cnf(c1,conjecture,(p)).\n", encoding="utf-8")

    matrix = matrix_from_file(problem, logic="classical")

    assert matrix.source_has_conjecture is False
    assert matrix.conjecture_clauses == (0,)


def test_matrix_from_file_python_emits_clausification_trace(tmp_path, caplog):
    problem = tmp_path / "trace_python.p"
    problem.write_text("fof(a1,axiom,p).\n", encoding="utf-8")
    caplog.set_level(TRACE_LEVEL, logger=CLAUSIFICATION_TRACE_LOGGER_NAME)

    matrix_from_file(
        problem,
        logic="classical",
    )

    assert caplog.messages[0] == "matrix.from_file.start"
    assert "clausification.document.start" in caplog.messages
    assert "clausification.done" in caplog.messages
    assert caplog.messages[-1] == "matrix.from_file.done"


def test_matrix_from_file_uses_explicit_source_file_dirs(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    included = lib_dir / "library.ax"
    included.write_text("fof(lib,axiom,q).\n", encoding="utf-8")

    problem = tmp_path / "uses_include.p"
    problem.write_text(
        "include('library.ax').\nfof(main,axiom,p).\n",
        encoding="utf-8",
    )

    matrix = matrix_from_file(
        problem,
        logic="classical",
        source_file_dirs=(lib_dir,),
    )

    assert len(matrix) > 0


def test_matrix_from_file_resolves_tptp_axioms_source_dir(tmp_path):
    tptp_root = tmp_path / "TPTP-v-test"
    axioms = tptp_root / "Axioms"
    problems = tptp_root / "Problems" / "SYN"
    axioms.mkdir(parents=True)
    problems.mkdir(parents=True)
    included = axioms / "SYN000+0.ax"
    included.write_text("fof(lib,axiom,q).\n", encoding="utf-8")

    problem = problems / "SYN000+1.p"
    problem.write_text(
        "include('Axioms/SYN000+0.ax').\nfof(main,conjecture,q).\n",
        encoding="utf-8",
    )

    matrix = matrix_from_file(
        problem,
        logic="classical",
        source_file_dirs=(axioms,),
    )

    assert len(matrix) > 0


def test_matrix_from_file_does_not_use_logic_env_by_default(tmp_path, monkeypatch):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    included = lib_dir / "library.ax"
    included.write_text("fof(lib,axiom,q).\n", encoding="utf-8")

    problem = tmp_path / "uses_include.p"
    problem.write_text(
        "include('library.ax').\nfof(main,axiom,p).\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TPTP", str(lib_dir))

    with pytest.raises(TPTPParseError):
        matrix_from_file(
            problem,
            logic="classical",
        )
