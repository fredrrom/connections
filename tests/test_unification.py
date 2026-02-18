from connections.logic.substitution import TermSubstitution
from connections.logic.syntax import Constant, Function, Variable


def test_unify_constants():
    sub = TermSubstitution()
    ok, updates = sub.unify(Constant("a"), Constant("a"))
    assert ok
    assert updates == []

    ok, updates = sub.unify(Constant("a"), Constant("b"))
    assert not ok
    assert updates == []


def test_unify_is_pure_until_update():
    sub = TermSubstitution()
    x = Variable("X", vid=1)
    a = Constant("a")

    ok, updates = sub.unify(x, a)
    assert ok
    assert sub._find(x) == x

    sub.update(updates)
    assert sub._find(x) == a


def test_update_and_revert():
    sub = TermSubstitution()
    x = Variable("X", vid=1)
    y = Variable("Y", vid=2)

    ok, updates = sub.unify(x, y)
    assert ok
    sub.update(updates)
    assert sub._find(y) == x

    sub.revert(updates)
    assert sub._find(x) == x
    assert sub._find(y) == y


def test_unify_functions_with_chain():
    sub = TermSubstitution()
    x = Variable("X", vid=1)
    y = Variable("Y", vid=2)
    a = Constant("a")

    left = Function("f", args=(x, y))
    right = Function("f", args=(y, a))

    ok, updates = sub.unify(left, right)
    assert ok
    sub.update(updates)

    assert sub._find(x) == a
    assert sub._find(y) == a


def test_occurs_check_strict():
    sub = TermSubstitution()
    x = Variable("X", vid=1)
    fx = Function("f", args=(x,))

    ok, updates = sub.unify(x, fx)
    assert not ok
    assert updates == []
