from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrefixCase:
    name: str
    logic: str
    domain: str
    left: str
    right: str
    expected: bool


@dataclass(frozen=True, slots=True)
class PrefixEquationCase:
    name: str
    logic: str
    domain: str
    equations: tuple[tuple[str, str], ...]
    expected: bool


@dataclass(frozen=True, slots=True)
class FreeVariableCase:
    name: str
    logic: str
    domain: str
    free_variables: tuple[tuple[str, str, str | None, str | None], ...]
    expected: bool


DEFAULT_PREFIX_CASES: tuple[PrefixCase, ...] = (
    PrefixCase(
        name="d_same_constants",
        logic="d",
        domain="cumul",
        left="-[a,b]",
        right="[a,b]",
        expected=True,
    ),
    PrefixCase(
        name="d_different_lengths_fail",
        logic="d",
        domain="cumul",
        left="-[a]",
        right="[a,b]",
        expected=False,
    ),
    PrefixCase(
        name="t_variable_single_step",
        logic="t",
        domain="cumul",
        left="-[X]",
        right="[a]",
        expected=True,
    ),
    PrefixCase(
        name="t_variable_not_transitive",
        logic="t",
        domain="cumul",
        left="-[X]",
        right="[a,b]",
        expected=False,
    ),
    PrefixCase(
        name="s4_variable_transitive_suffix",
        logic="s4",
        domain="cumul",
        left="-[X]",
        right="[a,b]",
        expected=True,
    ),
    PrefixCase(
        name="s4_ground_not_transitive_without_variable",
        logic="s4",
        domain="cumul",
        left="-[a]",
        right="[a,b]",
        expected=False,
    ),
    PrefixCase(
        name="s5_same_last_world",
        logic="s5",
        domain="cumul",
        left="-[a,b]",
        right="[c,b]",
        expected=True,
    ),
    PrefixCase(
        name="s5_different_last_world",
        logic="s5",
        domain="cumul",
        left="-[a,b]",
        right="[c,d]",
        expected=False,
    ),
    PrefixCase(
        name="s5_variable_last_world",
        logic="s5",
        domain="cumul",
        left="-[X]",
        right="[a,b]",
        expected=True,
    ),
    PrefixCase(
        name="intuitionistic_extends_negative_prefix",
        logic="intuitionistic",
        domain="cumul",
        left="-[a]",
        right="[a,b]",
        expected=True,
    ),
    PrefixCase(
        name="intuitionistic_ground_mismatch_fails",
        logic="intuitionistic",
        domain="cumul",
        left="-[c]",
        right="[a,b]",
        expected=False,
    ),
    PrefixCase(
        name="intuitionistic_variable_prefix",
        logic="intuitionistic",
        domain="cumul",
        left="-[X]",
        right="[a,b]",
        expected=True,
    ),
)


DEFAULT_FREE_VARIABLE_CASES: tuple[FreeVariableCase, ...] = (
    FreeVariableCase(
        name="const_ignores_variable_prefixes",
        logic="d",
        domain="const",
        free_variables=(("X", "[a]", None, None), ("X", "[b]", None, None)),
        expected=True,
    ),
    FreeVariableCase(
        name="varying_d_same_variable_same_prefix",
        logic="d",
        domain="vary",
        free_variables=(("X", "[a]", None, None), ("X", "[a]", None, None)),
        expected=True,
    ),
    FreeVariableCase(
        name="varying_d_same_variable_different_prefix",
        logic="d",
        domain="vary",
        free_variables=(("X", "[a]", None, None), ("X", "[b]", None, None)),
        expected=False,
    ),
    FreeVariableCase(
        name="cumulative_ignores_plain_variable_prefixes",
        logic="d",
        domain="cumul",
        free_variables=(("X", "[a]", None, None), ("X", "[b]", None, None)),
        expected=True,
    ),
    FreeVariableCase(
        name="cumulative_d_prefixed_term_at_later_prefix",
        logic="d",
        domain="cumul",
        free_variables=(("X", "[a,b]", "sk", "[a]"),),
        expected=True,
    ),
    FreeVariableCase(
        name="cumulative_d_prefixed_term_at_shorter_prefix_fails",
        logic="d",
        domain="cumul",
        free_variables=(("X", "[a]", "sk", "[a,b]"),),
        expected=False,
    ),
    FreeVariableCase(
        name="cumulative_s4_prefixed_term_at_extension",
        logic="s4",
        domain="cumul",
        free_variables=(("X", "[a,b]", "sk", "[a]"),),
        expected=True,
    ),
    FreeVariableCase(
        name="cumulative_s4_prefixed_term_mismatch_fails",
        logic="s4",
        domain="cumul",
        free_variables=(("X", "[a,b]", "sk", "[c]"),),
        expected=False,
    ),
    FreeVariableCase(
        name="cumulative_s5_prefixed_term_always_allowed",
        logic="s5",
        domain="cumul",
        free_variables=(("X", "[a,b]", "sk", "[c]"),),
        expected=True,
    ),
    FreeVariableCase(
        name="prefixed_term_arguments_do_not_add_varying_conditions",
        logic="d",
        domain="vary",
        free_variables=(
            ("Y", "[a]", "f(X)", "[a]"),
            ("X", "[b]", None, None),
        ),
        expected=True,
    ),
    FreeVariableCase(
        name="intuitionistic_plain_variables_are_unrestricted",
        logic="intuitionistic",
        domain="cumul",
        free_variables=(("X", "[a]", None, None), ("X", "[b]", None, None)),
        expected=True,
    ),
    FreeVariableCase(
        name="intuitionistic_prefixed_term_extends_prefix",
        logic="intuitionistic",
        domain="cumul",
        free_variables=(("X", "[a,b]", "sk", "[a]"),),
        expected=True,
    ),
    FreeVariableCase(
        name="intuitionistic_prefixed_term_mismatch_fails",
        logic="intuitionistic",
        domain="cumul",
        free_variables=(("X", "[a,b]", "sk", "[c]"),),
        expected=False,
    ),
    FreeVariableCase(
        name="intuitionistic_prefixed_term_arguments_do_not_add_conditions",
        logic="intuitionistic",
        domain="cumul",
        free_variables=(
            ("Y", "[a]", "f(X)", "[a]"),
            ("X", "[b]", None, None),
        ),
        expected=True,
    ),
)


DEFAULT_PREFIX_EQUATION_CASES: tuple[PrefixEquationCase, ...] = (
    PrefixEquationCase(
        name="d_shared_variable_consistent",
        logic="d",
        domain="cumul",
        equations=(("-[X]", "[a]"), ("-[X]", "[a]")),
        expected=True,
    ),
    PrefixEquationCase(
        name="d_shared_variable_conflict",
        logic="d",
        domain="cumul",
        equations=(("-[X]", "[a]"), ("-[X]", "[b]")),
        expected=False,
    ),
    PrefixEquationCase(
        name="t_empty_then_world_conflict",
        logic="t",
        domain="cumul",
        equations=(("-[X]", "[]"), ("-[X]", "[a]")),
        expected=False,
    ),
    PrefixEquationCase(
        name="s4_same_transitive_fragment",
        logic="s4",
        domain="cumul",
        equations=(("-[X]", "[a,b]"), ("-[X]", "[a,b]")),
        expected=True,
    ),
    PrefixEquationCase(
        name="s4_transitive_fragment_conflict",
        logic="s4",
        domain="cumul",
        equations=(("-[X]", "[a,b]"), ("-[X]", "[a,c]")),
        expected=False,
    ),
    PrefixEquationCase(
        name="s5_shared_last_world",
        logic="s5",
        domain="cumul",
        equations=(("-[X]", "[a,b]"), ("-[X]", "[c,b]")),
        expected=True,
    ),
    PrefixEquationCase(
        name="s5_different_last_world_conflict",
        logic="s5",
        domain="cumul",
        equations=(("-[X]", "[a,b]"), ("-[X]", "[c,d]")),
        expected=False,
    ),
    PrefixEquationCase(
        name="intuitionistic_same_ground_head",
        logic="intuitionistic",
        domain="cumul",
        equations=(("-[a]", "[a,b]"), ("-[a]", "[a,c]")),
        expected=True,
    ),
    PrefixEquationCase(
        name="intuitionistic_different_ground_head",
        logic="intuitionistic",
        domain="cumul",
        equations=(("-[a]", "[a,b]"), ("-[a]", "[c,d]")),
        expected=False,
    ),
)


__all__ = [
    "DEFAULT_FREE_VARIABLE_CASES",
    "DEFAULT_PREFIX_EQUATION_CASES",
    "DEFAULT_PREFIX_CASES",
    "FreeVariableCase",
    "PrefixCase",
    "PrefixEquationCase",
]
