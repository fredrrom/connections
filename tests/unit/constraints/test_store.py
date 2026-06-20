from __future__ import annotations

from connections.syntax.formula import Atom, Function, Prefix, Variable
from connections.syntax.matrix import Literal
from connections.constraints import ConstraintDelta, ConstraintStore, PrefixEquation


def lit(symbol: str, *args, polarity: bool = True) -> Literal:
    return Literal(Atom(symbol, args), polarity=polarity)


def test_constraint_store_commits_and_rolls_back_term_delta():
    variable = Variable("X")
    constant = Function("a")
    constraints = ConstraintStore()

    delta = constraints.delta_for_literals(
        older=lit("p", variable),
        older_instance=None,
        newer=lit("p", constant),
        newer_instance=None,
    )

    assert delta is not None
    assert delta.term_bindings == ((variable, (constant, None)),)

    constraints.commit(delta, owner_app_id=1)

    assert constraints.term_bindings == {variable: (constant, None)}
    assert constraints.revision == 1

    constraints.rollback_owned_by((1,))

    assert constraints.term_bindings == {}
    assert constraints.revision == 2


def test_constraint_store_returns_none_for_failed_unification():
    constraints = ConstraintStore()

    delta = constraints.delta_for_literals(
        older=lit("p", Function("a")),
        older_instance=None,
        newer=lit("p", Function("b")),
        newer_instance=None,
    )

    assert delta is None


def test_constraint_store_satisfied_literals_uses_current_term_substitution():
    variable = Variable("X")
    constant = Function("a")
    constraints = ConstraintStore()
    delta = constraints.delta_for_literals(
        older=lit("p", variable),
        older_instance=None,
        newer=lit("p", constant),
        newer_instance=None,
    )
    assert delta is not None

    constraints.commit(delta, owner_app_id=1)

    assert constraints.satisfied_literals(
        lit("p", variable),
        left_instance=None,
        right=lit("p", constant),
        right_instance=None,
    )


def test_constraint_store_commits_and_rolls_back_prefix_equations():
    variable = Variable("X")
    constant = Function("a")
    constraints = ConstraintStore()

    delta = constraints.delta_for_literals(
        older=Literal(Atom("p", ()), prefix=Prefix((variable,))),
        older_instance=None,
        newer=Literal(Atom("p", ()), prefix=Prefix((constant,))),
        newer_instance=None,
        logic="D",
        domain="cumulative",
    )

    assert delta is not None
    assert delta.term_bindings == ()
    assert delta.prefix_equations == (
        PrefixEquation(Prefix((variable,)), Prefix((constant,))),
    )

    constraints.commit(delta, owner_app_id=1)

    assert constraints.prefix_equations == delta.prefix_equations
    assert constraints.revision == 1
    assert constraints.satisfiable(logic="D", domain="cumulative")
    same_prefix_delta = constraints.delta_for_prefixes(
        Prefix((variable,)),
        Prefix((constant,)),
        logic="D",
        domain="cumulative",
    )
    assert same_prefix_delta is not None
    assert same_prefix_delta.prefix_equations == ()
    conflicting = constraints.delta_for_prefixes(
        Prefix((variable,)),
        Prefix((Function("b"),)),
        logic="D",
        domain="cumulative",
    )
    assert conflicting is not None

    constraints.commit(conflicting, owner_app_id=2)

    assert not constraints.satisfiable(logic="D", domain="cumulative")

    constraints.rollback_owned_by((1, 2))

    assert constraints.prefix_equations == ()
    assert constraints.revision == 3


def test_constraint_store_commits_and_rolls_back_free_variables():
    variable = Variable("X", prefix=Prefix((Function("a"),)))
    constraints = ConstraintStore()
    delta = ConstraintDelta(free_variables=((variable, 3),))

    constraints.commit(delta, owner_app_id=1)

    assert constraints.free_variables == ((variable, 3),)
    assert constraints.revision == 1

    constraints.rollback_owned_by((1,))

    assert constraints.free_variables == ()
    assert constraints.revision == 2


def test_constraint_store_rejects_inadmissible_varying_free_variables():
    first = Variable("X", prefix=Prefix((Function("a"),)))
    second = Variable("X", prefix=Prefix((Function("b"),)))
    constraints = ConstraintStore()

    delta = constraints.delta_for_free_variables(
        ((first, 1), (second, 1)),
        logic="D",
        domain="varying",
    )

    assert delta is None


def test_constraint_store_resolves_free_variables_with_pending_bindings():
    variable = Variable("X", prefix=Prefix((Function("a"),)))
    constraints = ConstraintStore()

    delta = constraints.delta_for_literals(
        older=lit("p", Function("sk", prefix=Prefix((Function("a"), Function("b"))))),
        older_instance=None,
        newer=lit("p", Variable("X")),
        newer_instance=1,
        logic="D",
        domain="cumulative",
        free_variables=((variable, 1),),
    )

    assert delta is None


def test_constraint_store_checks_active_free_variables_with_pending_bindings():
    variable = Variable("X", prefix=Prefix((Function("a"),)))
    constraints = ConstraintStore()
    constraints.commit(ConstraintDelta(free_variables=((variable, 1),)), owner_app_id=1)

    delta = constraints.delta_for_literals(
        older=lit("p", Function("sk", prefix=Prefix((Function("a"), Function("b"))))),
        older_instance=None,
        newer=lit("p", Variable("X")),
        newer_instance=1,
        logic="D",
        domain="cumulative",
    )

    assert delta is None


def test_constraint_store_free_variable_alias_uses_clause_prefix():
    variable = Variable("X", prefix=Prefix((Function("a"),)))
    constraints = ConstraintStore()

    delta = constraints.delta_for_literals(
        older=lit("p", Variable("Y")),
        older_instance=2,
        newer=lit("p", Variable("X")),
        newer_instance=1,
        logic="D",
        domain="varying",
        free_variables=((variable, 1),),
    )

    assert delta is not None
    assert delta.free_variables == ((variable, 1),)


def test_constraint_store_orients_intuitionistic_prefixes_by_literal_polarity():
    constraints = ConstraintStore()
    positive = Literal(
        Atom("p", ()),
        prefix=Prefix((Function("a"), Function("b"))),
        polarity=True,
    )
    negative = Literal(
        Atom("p", ()),
        prefix=Prefix((Function("a"),)),
        polarity=False,
    )

    delta = constraints.delta_for_literals(
        older=positive,
        older_instance=None,
        newer=negative,
        newer_instance=None,
        logic="intuitionistic",
        domain="cumulative",
    )

    assert delta is not None
    assert len(delta.prefix_equations) == 1
    assert delta.prefix_equations[0].left == negative.prefix
    assert delta.prefix_equations[0].right == positive.prefix


def test_constraint_store_satisfied_literals_does_not_solve_prefix_equations():
    variable = Variable("X")
    constant = Function("a")
    constraints = ConstraintStore()
    delta = constraints.delta_for_prefixes(
        Prefix((variable,)),
        Prefix((constant,)),
        logic="D",
        domain="cumulative",
    )
    assert delta is not None

    constraints.commit(delta, owner_app_id=1)

    assert not constraints.satisfied_literals(
        Literal(Atom("p", ()), prefix=Prefix((variable,))),
        left_instance=None,
        right=Literal(Atom("p", ()), prefix=Prefix((constant,))),
        right_instance=None,
        logic="D",
        domain="cumulative",
    )


def test_constraint_store_prefix_equations_are_instance_scoped():
    variable = Variable("X")
    constraints = ConstraintStore()

    first = constraints.delta_for_prefixes(
        Prefix((variable,)),
        Prefix((Function("a"),)),
        older_instance=1,
        logic="D",
        domain="cumulative",
    )
    assert first is not None
    constraints.commit(first, owner_app_id=1)

    second = constraints.delta_for_prefixes(
        Prefix((variable,)),
        Prefix((Function("b"),)),
        older_instance=2,
        logic="D",
        domain="cumulative",
    )

    assert second is not None
