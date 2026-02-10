from connections.logic.syntax import Constant, Function, Variable
from connections.logic.substitution import Substitution


def test_unify_constants():
    sub = Substitution()
    ok, updates = sub.can_unify(Constant("a"), Constant("a"))
    assert ok
    assert updates == []

    ok, updates = sub.can_unify(Constant("a"), Constant("b"))
    assert not ok
    assert updates == []


def test_unify_variable_ordering_and_cut():
    sub = Substitution()
    x = Variable("X", vid=1)
    y = Variable("Y", vid=2)

    ok, updates = sub.can_unify(x, y)
    assert ok
    sub.update(updates)

    assert sub.find(y) == x
    assert sub.find(x) == x

    sub.cut(updates)
    assert sub.find(x) == x
    assert sub.find(y) == y


def test_unify_functions_with_chain():
    sub = Substitution()
    x = Variable("X", vid=1)
    y = Variable("Y", vid=2)
    a = Constant("a")

    left = Function("f", args=(x, y))
    right = Function("f", args=(y, a))

    ok, updates = sub.can_unify(left, right)
    assert ok
    sub.update(updates)

    assert sub.find(x) == a
    assert sub.find(y) == a


def test_occurs_check_strict():
    sub = Substitution()
    x = Variable("X", vid=1)
    fx = Function("f", args=(x,))

    ok, updates = sub.can_unify(x, fx)
    assert not ok
    assert updates == []


def test_cut_removes_bindings():
    sub = Substitution()
    x = Variable("X", vid=1)
    a = Constant("a")

    ok, updates = sub.unify(x, a)
    assert ok
    assert sub.find(x) == a

    sub.cut(updates)
    assert sub.find(x) == x
