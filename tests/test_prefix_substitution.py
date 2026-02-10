import pytest

from connections.logic.prefix_substitution import PrefixSubstitution
from connections.logic.substitution import Substitution
from connections.logic.syntax import Constant, Function, Literal, Prefix, Variable


def test_prefix_unify_intuitionistic_success():
    prefix_sub = PrefixSubstitution(logic="intuitionistic")
    term_sub = Substitution()
    left = Prefix((Variable("A"), Variable("B"), Variable("C")))
    right = Prefix((Function("a"), Function("b"), Function("c")))
    assert prefix_sub.unify(left, right, term_sub) is not None


def test_prefix_unify_t_success():
    prefix_sub = PrefixSubstitution(logic="T")
    term_sub = Substitution()
    left = Prefix((Variable("A"), Variable("B"), Variable("C")))
    right = Prefix((Variable("E"), Variable("F"), Variable("G")))
    assert prefix_sub.unify(left, right, term_sub) is not None


def test_prefix_unify_pairs_intuitionistic_success():
    prefix_sub = PrefixSubstitution(logic="intuitionistic")
    term_sub = Substitution()

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

    a_3 = Function("c_skolem", args=(Constant("1"), Constant("a")))
    b_3 = Function(
        "f", args=(Function("f_skolem", args=(Constant("1"), Constant("a"))),)
    )
    c_3 = Function("c_skolem", args=(Constant("2"), b_3, Constant("a")))
    pre_3 = Prefix((a_3, c_3))

    assert (
        prefix_sub.unify_pairs([(pre_1, pre_2), (pre_2, pre_3)], term_sub) is not None
    )


def test_prefix_unify_pairs_t_success():
    prefix_sub = PrefixSubstitution(logic="T")
    term_sub = Substitution()
    left = Prefix(
        (
            Function(
                "c_skolem",
                args=(Function("1"), Function("c_skolem", args=(Function("2"),))),
            ),
        )
    )
    right = Prefix((Function("c_skolem", args=(Function("1"), Variable("_76862"))),))
    assert prefix_sub.unify_pairs([(left, right)], term_sub) is not None


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


def test_admissible_pair_dispatch_d_cumulative_truncates_left():
    prefix_sub = PrefixSubstitution(logic="D", domain="cumulative")
    left = Prefix((Function("w1"), Function("w2"), Function("w3")))
    right = Prefix((Function("v1"), Function("v2")))

    pair = prefix_sub.admissible_pair(left, right)

    assert pair == (Prefix((Function("w1"), Function("w2"))), right)
