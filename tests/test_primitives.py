from connections.logic.syntax import Clause, Function, Literal, Matrix, Variable


def test_variable_str_with_id():
    x = Variable("X", vid=1)
    assert str(x) == "X1"


def test_function_str():
    x = Variable("X")
    f = Function("f", (x,))
    assert str(f) == "f(X)"


def test_literal_str_and_negation():
    x = Variable("X")
    f = Function("f", (x,))
    pos = Literal("p", (f,))
    neg = Literal("p", (f,), neg=True)
    assert str(pos) == "p(f(X))"
    assert str(neg) == "-p(f(X))"


def test_matrix_complements():
    x = Variable("X")
    f = Function("f", (x,))
    p = Literal("p", (f,))
    q = Literal("p", (f,), neg=True)
    matrix = Matrix((Clause((p,)), Clause((q,))))
    assert matrix.complements(p) == ((1, 0),)
