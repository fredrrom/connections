from __future__ import annotations

from typing import Iterable

from connections.core.formula import (
    And,
    Atom,
    Box,
    Diamond,
    Eq,
    Exists,
    Forall,
    Formula,
    Function,
    Iff,
    Impl,
    Not,
    Or,
    Term,
    Variable,
)


def univar(formula: Formula) -> Formula:
    counter = 1

    def fresh() -> Variable:
        nonlocal counter
        variable = Variable(f"V{counter}")
        counter += 1
        return variable

    def map_term(term: Term, mapping: dict[str, Variable]) -> Term:
        if isinstance(term, Variable):
            return mapping.get(term.symbol, term)
        if isinstance(term, Function):
            return Function(
                term.symbol,
                tuple(map_term(arg, mapping) for arg in term.args),
                term.prefix,
            )
        return term

    def map_formula(current: Formula, mapping: dict[str, Variable]) -> Formula:
        if isinstance(current, Atom):
            return Atom(
                current.symbol,
                tuple(map_term(arg, mapping) for arg in current.args),
            )
        if isinstance(current, Eq):
            return Eq(map_term(current.left, mapping), map_term(current.right, mapping))
        if isinstance(current, Not):
            return Not(map_formula(current.formula, mapping))
        if isinstance(current, And):
            return And(
                map_formula(current.left, mapping),
                map_formula(current.right, mapping),
            )
        if isinstance(current, Or):
            return Or(
                map_formula(current.left, mapping),
                map_formula(current.right, mapping),
            )
        if isinstance(current, Impl):
            return Impl(
                map_formula(current.left, mapping),
                map_formula(current.right, mapping),
            )
        if isinstance(current, Iff):
            return Iff(
                map_formula(current.left, mapping),
                map_formula(current.right, mapping),
            )
        if isinstance(current, Exists):
            renamed = fresh()
            next_mapping = dict(mapping)
            next_mapping[current.variable.symbol] = renamed
            return Exists(renamed, map_formula(current.body, next_mapping))
        if isinstance(current, Forall):
            renamed = fresh()
            next_mapping = dict(mapping)
            next_mapping[current.variable.symbol] = renamed
            return Forall(renamed, map_formula(current.body, next_mapping))
        if isinstance(current, Box):
            index = (
                map_term(current.index, mapping)
                if current.index is not None
                else None
            )
            return Box(map_formula(current.body, mapping), index=index)
        if isinstance(current, Diamond):
            index = (
                map_term(current.index, mapping)
                if current.index is not None
                else None
            )
            return Diamond(map_formula(current.body, mapping), index=index)
        raise TypeError(f"Unsupported formula node: {type(current)!r}")

    return map_formula(formula, {})


def contains_modal_formula(formula: Formula) -> bool:
    stack = [formula]
    while stack:
        current = stack.pop()
        if isinstance(current, (Box, Diamond)):
            return True
        if isinstance(current, Not):
            stack.append(current.formula)
            continue
        if isinstance(current, (And, Or, Impl, Iff)):
            stack.append(current.right)
            stack.append(current.left)
            continue
        if isinstance(current, (Forall, Exists)):
            stack.append(current.body)
    return False


def substitute_variable(formula: Formula, var_name: str, replacement: Term) -> Formula:
    def subst_term(term: Term) -> Term:
        if isinstance(term, Variable):
            if term.symbol == var_name:
                return replacement
            return term
        if isinstance(term, Function):
            return Function(
                term.symbol,
                tuple(subst_term(arg) for arg in term.args),
                term.prefix,
            )
        return term

    if isinstance(formula, Atom):
        return Atom(formula.symbol, tuple(subst_term(arg) for arg in formula.args))
    if isinstance(formula, Eq):
        return Eq(subst_term(formula.left), subst_term(formula.right))
    if isinstance(formula, Not):
        return Not(substitute_variable(formula.formula, var_name, replacement))
    if isinstance(formula, And):
        return And(
            substitute_variable(formula.left, var_name, replacement),
            substitute_variable(formula.right, var_name, replacement),
        )
    if isinstance(formula, Or):
        return Or(
            substitute_variable(formula.left, var_name, replacement),
            substitute_variable(formula.right, var_name, replacement),
        )
    if isinstance(formula, Impl):
        return Impl(
            substitute_variable(formula.left, var_name, replacement),
            substitute_variable(formula.right, var_name, replacement),
        )
    if isinstance(formula, Iff):
        return Iff(
            substitute_variable(formula.left, var_name, replacement),
            substitute_variable(formula.right, var_name, replacement),
        )
    if isinstance(formula, Exists):
        if formula.variable.symbol == var_name:
            return formula
        return Exists(
            formula.variable,
            substitute_variable(formula.body, var_name, replacement),
        )
    if isinstance(formula, Forall):
        if formula.variable.symbol == var_name:
            return formula
        return Forall(
            formula.variable,
            substitute_variable(formula.body, var_name, replacement),
        )
    if isinstance(formula, Box):
        index = subst_term(formula.index) if formula.index is not None else None
        return Box(substitute_variable(formula.body, var_name, replacement), index)
    if isinstance(formula, Diamond):
        index = subst_term(formula.index) if formula.index is not None else None
        return Diamond(
            substitute_variable(formula.body, var_name, replacement),
            index,
        )
    raise TypeError(f"Unsupported formula node: {type(formula)!r}")


def combine_with_and(formulas: Iterable[Formula]) -> Formula:
    formula_list = list(formulas)
    if not formula_list:
        raise ValueError("Expected at least one formula")
    result = formula_list[-1]
    for formula in reversed(formula_list[:-1]):
        result = And(formula, result)
    return result


__all__ = [
    "combine_with_and",
    "contains_modal_formula",
    "substitute_variable",
    "univar",
]
