from __future__ import annotations

from connections.syntax.formula import Atom, Function, Prefix, Variable
from connections.syntax.matrix import Clause, Literal, Matrix, SignedPredicateSymbol
from connections.prover.prover import Problem


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


def test_matrix_complements():
    x = Variable("X")
    f = Function("f", (x,))
    p = Literal(atom=Atom("p", (f,)), polarity=True)
    q = Literal(atom=Atom("p", (f,)), polarity=False)
    matrix = Matrix((Clause((p,)), Clause((q,))))
    _assert_matrix_indices_consistent(matrix)
    assert matrix.statically_filtered_connection_graph == {}
    assert matrix.complements(0, 0) == ((1, 0),)
    assert matrix.statically_filtered_connection_graph[(0, 0)] == ((1, 0),)


def test_matrix_complements_prunes_empty_substitution_failures():
    x = Variable("X")
    y = Variable("Y")
    z = Variable("Z")
    p = Literal(atom=Atom("p", (Function("f", (x,)), y)), polarity=True)
    incompatible_head = Literal(
        atom=Atom("p", (Function("g", (x,)), z)),
        polarity=False,
    )
    compatible_ground = Literal(
        atom=Atom("p", (Function("f", (Function("a"),)), Function("b"))),
        polarity=False,
    )
    compatible_variable = Literal(
        atom=Atom("p", (Variable("W"), Function("b"))),
        polarity=False,
    )
    matrix = Matrix(
        (
            Clause((p,)),
            Clause((incompatible_head,)),
            Clause((compatible_ground,)),
            Clause((compatible_variable,)),
        )
    )

    _assert_matrix_indices_consistent(matrix)
    assert matrix.connection_graph[p.complement_symbol] == ((1, 0), (2, 0), (3, 0))
    assert matrix.statically_filtered_connection_graph == {}
    assert matrix.complements(0, 0) == ((2, 0), (3, 0))
    assert matrix.statically_filtered_connection_graph[(0, 0)] == ((2, 0), (3, 0))


def test_matrix_complements_prunes_repeated_variable_failures():
    x = Variable("X")
    p = Literal(atom=Atom("p", (x, x)), polarity=True)
    incompatible = Literal(
        atom=Atom("p", (Function("a"), Function("b"))),
        polarity=False,
    )
    compatible = Literal(
        atom=Atom("p", (Function("a"), Function("a"))),
        polarity=False,
    )
    matrix = Matrix((Clause((p,)), Clause((incompatible,)), Clause((compatible,))))

    _assert_matrix_indices_consistent(matrix)
    assert matrix.statically_filtered_connection_graph == {}
    assert matrix.complements(0, 0) == ((2, 0),)
    assert matrix.statically_filtered_connection_graph[(0, 0)] == ((2, 0),)


def test_matrix_complements_renames_variables_apart_between_sides():
    x = Variable("X")
    p = Literal(atom=Atom("p", (x,)), polarity=True)
    q = Literal(atom=Atom("p", (Function("f", (x,)),)), polarity=False)
    matrix = Matrix((Clause((p,)), Clause((q,))))

    _assert_matrix_indices_consistent(matrix)
    assert matrix.complements(0, 0) == ((1, 0),)


def test_matrix_basic_indexing_and_iteration():
    lit = Literal(atom=Atom("p"), polarity=True)
    clause = Clause((lit,))
    matrix = Matrix((clause,))
    assert len(matrix) == 1
    assert matrix[0] == clause
    assert matrix[0, 0] == lit
    assert list(iter(matrix)) == [clause]
    _assert_matrix_indices_consistent(matrix)


def test_clause_tracks_groundedness():
    ground_clause = Clause((Literal(atom=Atom("p", (Function("a"),))),))
    nonground_clause = Clause((Literal(atom=Atom("p", (Variable("X"),))),))

    assert ground_clause.is_ground is True
    assert nonground_clause.is_ground is False


def test_clause_carries_free_variables():
    prefix = Prefix((Function("a"),))
    variable = Variable("X", prefix=prefix)
    clause = Clause(
        (Literal(atom=Atom("p", (Variable("X"),))),), free_variables=(variable,)
    )

    assert clause.free_variables == (variable,)


def test_matrix_start_clauses_positive_mode_selects_positive_clauses():
    pos = Clause((Literal(atom=Atom("p"), polarity=True),))
    neg = Clause((Literal(atom=Atom("q"), polarity=False),))
    conj = Clause((Literal(atom=Atom("r"), polarity=True),), role="conjecture")
    matrix = Matrix((pos, neg, conj))
    _assert_matrix_indices_consistent(matrix)
    assert matrix.positive_clauses == (0, 2)
    assert matrix.conjecture_clauses == (2,)

def test_problem_conjecture_start_falls_back_to_positive_clauses():
    matrix = Matrix((Clause((Literal(atom=Atom("p"), polarity=True),)),))
    problem = Problem(matrix=matrix, start_clauses="conjecture")

    assert problem.start_clause_ids == (0,)


def test_problem_start_clause_indices_use_conjecture_clauses_when_requested():
    ax = Clause((Literal(atom=Atom("p"), polarity=True),), role="axiom")
    conj = Clause((Literal(atom=Atom("q"), polarity=True),), role="conjecture")
    matrix = Matrix((ax, conj))
    problem = Problem(matrix=matrix, start_clauses="conjecture")

    assert problem.start_clause_ids == (1,)
    starts = [clause_idx for clause_idx in problem.start_clause_ids]
    assert len(starts) == 1
    assert isinstance(starts[0], int)
    assert matrix.clauses[starts[0]].literals[0].atom.symbol == "q"


def test_matrix_tracks_positive_and_conjecture_clauses_on_direct_init():
    pos = Clause((Literal(atom=Atom("p"), polarity=True),), role="axiom")
    neg = Clause((Literal(atom=Atom("n"), polarity=False),), role="axiom")
    conj = Clause((Literal(atom=Atom("c"), polarity=True),), role="conjecture")
    matrix = Matrix((pos, neg, conj))
    _assert_matrix_indices_consistent(matrix)
    assert matrix.positive_clauses == (0, 2)
    assert matrix.conjecture_clauses == (2,)
