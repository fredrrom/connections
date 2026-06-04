from __future__ import annotations

import pytest

from connections.core.formula import Function, Prefix, Variable
from connections.constraints.prefix import (
    PrefixBinding,
    PrefixConstraintStore,
    PrefixEquation,
    free_variables_admissible,
    prefixes_admissible,
    prefix_equations_satisfiable,
    prefix_unify_from_empty,
    prefix_unifiable_from_empty,
)


def test_d_prefix_unification_requires_same_length():
    assert (
        prefix_unifiable_from_empty(
            Prefix((Function("a"),)),
            Prefix((Function("a"), Function("b"))),
            logic="D",
            domain="cumulative",
        )
        is False
    )


def test_d_prefix_unification_uses_first_order_unification():
    left = Prefix((Variable("X"), Function("b")))
    right = Prefix((Function("a"), Function("b")))

    assert (
        prefix_unifiable_from_empty(
            left,
            right,
            logic="D",
            domain="cumulative",
        )
        is True
    )


def test_d_prefix_unification_returns_bindings():
    variable = Variable("X")
    constant = Function("a")

    assert prefix_unify_from_empty(
        Prefix((variable, Function("b"))),
        Prefix((constant, Function("b"))),
        logic="D",
        domain="cumulative",
    ) == (PrefixBinding(variable, (constant,)),)


def test_d_prefix_unification_preserves_repeated_variables():
    left = Prefix((Variable("X"), Variable("X")))
    right = Prefix((Function("a"), Function("b")))

    assert (
        prefix_unifiable_from_empty(
            left,
            right,
            logic="D",
            domain="cumulative",
        )
        is False
    )


def test_d_prefix_unification_preserves_variables_across_both_sides():
    variable = Variable("X")

    assert (
        prefix_unifiable_from_empty(
            Prefix((Function("a"), variable)),
            Prefix((variable, Function("b"))),
            logic="D",
            domain="cumulative",
        )
        is False
    )


def test_t_prefix_variable_absorbs_zero_or_one_world():
    assert (
        prefix_unifiable_from_empty(
            Prefix((Variable("X"),)),
            Prefix((Function("a"),)),
            logic="T",
            domain="cumulative",
        )
        is True
    )
    assert (
        prefix_unifiable_from_empty(
            Prefix((Variable("X"),)),
            Prefix((Function("a"), Function("b"))),
            logic="T",
            domain="cumulative",
        )
        is False
    )


def test_t_prefix_unification_returns_empty_or_singleton_bindings():
    variable = Variable("X")
    constant = Function("a")

    assert prefix_unify_from_empty(
        Prefix((variable,)),
        Prefix(()),
        logic="T",
        domain="cumulative",
    ) == (PrefixBinding(variable, ()),)
    assert prefix_unify_from_empty(
        Prefix((variable,)),
        Prefix((constant,)),
        logic="T",
        domain="cumulative",
    ) == (PrefixBinding(variable, (constant,)),)


def test_s4_prefix_variable_absorbs_transitive_suffix():
    assert (
        prefix_unifiable_from_empty(
            Prefix((Variable("X"),)),
            Prefix((Function("a"), Function("b"))),
            logic="S4",
            domain="cumulative",
        )
        is True
    )
    assert (
        prefix_unifiable_from_empty(
            Prefix((Function("a"),)),
            Prefix((Function("a"), Function("b"))),
            logic="S4",
            domain="cumulative",
        )
        is False
    )


def test_s4_prefix_unification_returns_transitive_fragment_binding():
    variable = Variable("X")
    left = Prefix((variable,))
    right = Prefix((Function("a"), Function("b")))

    assert prefix_unify_from_empty(left, right, logic="S4", domain="cumulative") == (
        PrefixBinding(variable, right.parts),
    )


def test_s5_prefix_unification_uses_last_world():
    assert (
        prefix_unifiable_from_empty(
            Prefix((Function("a"), Function("b"))),
            Prefix((Function("c"), Function("b"))),
            logic="S5",
            domain="cumulative",
        )
        is True
    )
    assert (
        prefix_unifiable_from_empty(
            Prefix((Function("a"), Function("b"))),
            Prefix((Function("c"), Function("d"))),
            logic="S5",
            domain="cumulative",
        )
        is False
    )


def test_s5_prefix_unification_returns_last_world_binding():
    variable = Variable("X")
    last = Function("b")

    assert prefix_unify_from_empty(
        Prefix((variable,)),
        Prefix((Function("a"), last)),
        logic="S5",
        domain="cumulative",
    ) == (PrefixBinding(variable, (last,)),)


def test_intuitionistic_prefix_unification_extends_negative_prefix():
    assert prefix_unifiable_from_empty(
        Prefix((Function("a"),)),
        Prefix((Function("a"), Function("b"))),
        logic="intuitionistic",
        domain="cumulative",
    )
    assert not prefix_unifiable_from_empty(
        Prefix((Function("c"),)),
        Prefix((Function("a"), Function("b"))),
        logic="intuitionistic",
        domain="cumulative",
    )


def test_intuitionistic_prefix_unification_hides_internal_tail_variable():
    variable = Variable("X")
    assert prefix_unify_from_empty(
        Prefix((variable,)),
        Prefix((Function("a"), Function("b"))),
        logic="intuitionistic",
        domain="cumulative",
    ) == (PrefixBinding(variable, ()),)


def test_prefix_equation_set_satisfiability_shares_variables():
    variable = Variable("X")
    constant = Function("a")

    assert prefix_equations_satisfiable(
        (
            PrefixEquation(Prefix((variable,)), Prefix((constant,))),
            PrefixEquation(Prefix((variable,)), Prefix((constant,))),
        ),
        logic="D",
        domain="cumulative",
    )
    assert not prefix_equations_satisfiable(
        (
            PrefixEquation(Prefix((variable,)), Prefix((constant,))),
            PrefixEquation(Prefix((variable,)), Prefix((Function("b"),))),
        ),
        logic="D",
        domain="cumulative",
    )


def test_prefix_equation_set_handles_tuple_bound_variable_inside_function():
    variable = Variable("X")

    assert not prefix_equations_satisfiable(
        (
            PrefixEquation(
                Prefix((variable,)),
                Prefix((Function("a"), Function("b"))),
            ),
            PrefixEquation(
                Prefix((Function("f", (variable,)),)),
                Prefix((Function("f", (Function("a"),)),)),
            ),
        ),
        logic="intuitionistic",
        domain="cumulative",
    )


def test_prefix_constraint_store_commits_and_rolls_back_equations():
    variable = Variable("X")
    constant = Function("a")
    prefixes = PrefixConstraintStore()
    equations = prefixes.delta_for(
        Prefix((variable,)),
        None,
        Prefix((constant,)),
        None,
        logic="D",
        domain="cumulative",
    )

    assert equations == (
        PrefixEquation(Prefix((variable,)), Prefix((constant,))),
    )
    assert equations is not None

    prefixes.commit(equations, owner_app_id=1)

    assert prefixes.equations == equations
    assert prefixes.revision == 1
    assert prefixes.satisfiable(logic="D", domain="cumulative")
    assert (
        prefixes.delta_for(
            Prefix((variable,)),
            None,
            Prefix((constant,)),
            None,
            logic="D",
            domain="cumulative",
        )
        == ()
    )
    conflicting = prefixes.delta_for(
        Prefix((variable,)),
        None,
        Prefix((Function("b"),)),
        None,
        logic="D",
        domain="cumulative",
    )
    assert conflicting is not None

    prefixes.commit(conflicting, owner_app_id=2)

    assert not prefixes.satisfiable(logic="D", domain="cumulative")

    prefixes.rollback_owned_by((1, 2))

    assert prefixes.equations == ()
    assert prefixes.revision == 3


def test_prefix_constraint_store_scopes_variables_by_instance():
    variable = Variable("X")
    prefixes = PrefixConstraintStore()
    first = prefixes.delta_for(
        Prefix((variable,)),
        1,
        Prefix((Function("a"),)),
        None,
        logic="D",
        domain="cumulative",
    )
    assert first is not None
    prefixes.commit(first, owner_app_id=1)

    second = prefixes.delta_for(
        Prefix((variable,)),
        2,
        Prefix((Function("b"),)),
        None,
        logic="D",
        domain="cumulative",
    )

    assert second is not None


def test_varying_free_variables_track_first_variable_prefix():
    first = Variable("X", prefix=Prefix((Function("a"),)))

    assert free_variables_admissible(
        (
            first,
            first,
        ),
        logic="D",
        domain="varying",
    )
    assert not free_variables_admissible(
        (
            first,
            Variable("X", prefix=Prefix((Function("b"),))),
        ),
        logic="D",
        domain="varying",
    )


def test_cumulative_free_variables_ignore_plain_variable_prefixes():
    assert free_variables_admissible(
        (
            Variable("X", prefix=Prefix((Function("a"),))),
            Variable("X", prefix=Prefix((Function("b"),))),
        ),
        logic="D",
        domain="cumulative",
    )


def test_cumulative_free_variables_check_resolved_prefixed_terms():
    first = Variable("X", prefix=Prefix((Function("a"), Function("b"))))
    second = Variable("X", prefix=Prefix((Function("a"),)))

    assert free_variables_admissible(
        (first,),
        logic="D",
        domain="cumulative",
        resolved_terms={
            first: Function("sk", prefix=Prefix((Function("a"),))),
        },
    )
    assert not free_variables_admissible(
        (second,),
        logic="D",
        domain="cumulative",
        resolved_terms={
            second: Function("sk", prefix=Prefix((Function("a"), Function("b")))),
        },
    )


def test_free_variables_must_carry_prefixes():
    with pytest.raises(ValueError):
        free_variables_admissible(
            (Variable("X"),),
            logic="D",
            domain="cumulative",
        )


def test_prefixed_resolved_term_does_not_recurse_into_arguments():
    resolved_variable = Variable("Y", prefix=Prefix((Function("a"),)))
    argument_variable = Variable("X", prefix=Prefix((Function("b"),)))

    assert free_variables_admissible(
        (
            resolved_variable,
            argument_variable,
        ),
        logic="D",
        domain="varying",
        resolved_terms={
            resolved_variable: Function(
                "f",
                (Variable("X"),),
                prefix=Prefix((Function("a"),)),
            ),
        },
    )


def test_prefix_admissibility_uses_cumulative_prefix_relation():
    assert prefixes_admissible(
        Prefix((Function("a"),)),
        Prefix((Function("a"), Function("b"))),
        logic="D",
        domain="cumulative",
    )
    assert not prefixes_admissible(
        Prefix((Function("a"), Function("b"))),
        Prefix((Function("a"),)),
        logic="D",
        domain="cumulative",
    )


def test_intuitionistic_free_variables_check_resolved_prefixed_terms():
    first = Variable("X", prefix=Prefix((Function("a"), Function("b"))))
    second = Variable("X", prefix=Prefix((Function("a"), Function("b"))))

    assert free_variables_admissible(
        (first,),
        logic="intuitionistic",
        domain="cumulative",
        resolved_terms={
            first: Function("sk", prefix=Prefix((Function("a"),))),
        },
    )
    assert not free_variables_admissible(
        (second,),
        logic="intuitionistic",
        domain="cumulative",
        resolved_terms={
            second: Function("sk", prefix=Prefix((Function("c"),))),
        },
    )


def test_unsupported_prefix_logic_is_explicit():
    with pytest.raises(NotImplementedError):
        prefix_unifiable_from_empty(
            Prefix((Variable("X"),)),
            Prefix((Function("a"),)),
            logic="linear",
            domain="cumulative",
        )
