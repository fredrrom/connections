import pytest

from connections.logic.substitution import PrefixSubstitution, TermSubstitution
from connections.logic.syntax import Constant, Function, Literal, Prefix, Variable


def test_prefix_unify_intuitionistic_success():
    prefix_sub = PrefixSubstitution(logic="intuitionistic")
    term_sub = TermSubstitution()
    prefix_sub.bind_term_substitution(term_sub)
    left = Prefix((Variable("A"), Variable("B"), Variable("C")))
    right = Prefix((Function("a"), Function("b"), Function("c")))
    ok, _ = prefix_sub.unify(left, right)
    assert ok


def test_prefix_unify_t_success():
    prefix_sub = PrefixSubstitution(logic="T")
    term_sub = TermSubstitution()
    prefix_sub.bind_term_substitution(term_sub)
    left = Prefix((Variable("A"), Variable("B"), Variable("C")))
    right = Prefix((Variable("E"), Variable("F"), Variable("G")))
    ok, _ = prefix_sub.unify(left, right)
    assert ok


def test_prefix_unify_is_pure_until_update():
    prefix_sub = PrefixSubstitution(logic="D", domain="varying")
    term_sub = TermSubstitution()
    prefix_sub.bind_term_substitution(term_sub)
    x = Variable("X", vid=1)
    left = Prefix((x,))
    right = Prefix((Function("w"),))

    ok, updates = prefix_sub.unify(left, right)
    assert ok
    assert x not in prefix_sub.bindings

    prefix_sub.update(updates)
    assert x in prefix_sub.bindings

    prefix_sub.revert(updates)
    assert x not in prefix_sub.bindings


def test_prefix_unify_pairs_intuitionistic_success():
    prefix_sub = PrefixSubstitution(logic="intuitionistic")
    term_sub = TermSubstitution()
    prefix_sub.bind_term_substitution(term_sub)

    a_1 = Function("c_skolem", args=(Constant("1"), Constant("a")))
    b_1 = Function(
        "h", args=(Function("f_skolem", args=(Constant("1"), Constant("a"))),)
    )
    c_1 = Function("c_skolem", args=(Constant("2"), b_1, Constant("a")))
    pre_1 = Prefix((a_1, c_1))

    a_2 = Function("c_skolem", args=(Constant("1"), Constant("a")))
    b_2 = Variable("V")
    c_2 = Function("c_skolem", args=(Constant("2"), b_2, Constant("a")))
    pre_2 = Prefix((a_2, c_2))

    ok_1, updates_1 = prefix_sub.unify(pre_1, pre_2)
    assert ok_1
    prefix_sub.update(updates_1)

    a_3 = Function("c_skolem", args=(Constant("1"), Constant("a")))
    b_3 = Function(
        "f", args=(Function("f_skolem", args=(Constant("1"), Constant("a"))),)
    )
    c_3 = Function("c_skolem", args=(Constant("2"), b_3, Constant("a")))
    pre_3 = Prefix((a_3, c_3))

    ok_2, _ = prefix_sub.unify(pre_2, pre_3)
    assert ok_2


@pytest.mark.parametrize(
    ("logic", "domain", "expected"),
    [
        ("classical", "constant", False),
        ("intuitionistic", "constant", True),
        ("D", "constant", False),
        ("D", "cumulative", True),
        ("T", "constant", False),
        ("T", "varying", True),
        ("S4", "constant", False),
        ("S4", "cumulative", True),
        ("S5", "constant", False),
        ("S5", "cumulative", False),
        ("S5", "varying", True),
    ],
)
def test_should_collect_admissible_pairs_dispatch(
    logic: str, domain: str, expected: bool
):
    prefix_sub = PrefixSubstitution(logic=logic, domain=domain)
    assert prefix_sub.should_collect_admissible_pairs() is expected


def test_relation_pair_dispatch_intuitionistic_adds_fresh_on_negative_left():
    prefix_sub = PrefixSubstitution(logic="intuitionistic")
    left_lit = Literal("p", neg=True, prefix=Prefix((Function("w1"),)))
    right_lit = Literal("p", neg=False, prefix=Prefix((Function("w2"),)))

    left_prefix, right_prefix = prefix_sub.relation_pair(
        left_lit,
        right_lit,
        fresh_variable=Variable("W1"),
    )

    assert left_prefix.parts[-1] == Variable("W1")
    assert right_prefix == Prefix((Function("w2"),))


def test_relation_pair_dispatch_s5_keeps_last_world_only():
    prefix_sub = PrefixSubstitution(logic="S5")
    left_lit = Literal("p", prefix=Prefix((Function("w1"), Function("w2"))))
    right_lit = Literal("p", prefix=Prefix((Function("v1"), Function("v2"))))

    left_prefix, right_prefix = prefix_sub.relation_pair(left_lit, right_lit)

    assert left_prefix == Prefix((Function("w2"),))
    assert right_prefix == Prefix((Function("v2"),))
