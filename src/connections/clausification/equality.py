from __future__ import annotations

from collections.abc import Sequence

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
from connections.clausification.formula_ops import combine_with_and


def add_equality_axioms(formula: Formula) -> Formula:
    predicates, functions, has_equality = _collect_predfunc(formula)
    if not has_equality:
        return formula

    equality_block = combine_with_and(_basic_equality_axioms())
    pred_axioms = _subst_pred_axioms(predicates)
    if pred_axioms:
        equality_block = And(equality_block, combine_with_and(pred_axioms))
    func_axioms = _subst_func_axioms(functions)
    if func_axioms:
        equality_block = And(equality_block, combine_with_and(func_axioms))

    if isinstance(formula, Impl):
        return Impl(And(equality_block, formula.left), formula.right)
    return Impl(equality_block, formula)


def _collect_predfunc(
    formula: Formula,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]], bool]:
    predicates: list[tuple[str, int]] = []
    functions: list[tuple[str, int]] = []
    has_equality = False
    stack: list[tuple[str, Formula | Term]] = [("formula", formula)]

    while stack:
        kind, node = stack.pop()
        if kind == "term":
            if isinstance(node, Function):
                arity = len(node.args)
                if arity > 0:
                    functions.append((node.symbol, arity))
                    for arg in reversed(node.args):
                        stack.append(("term", arg))
            continue

        assert isinstance(
            node,
            (Atom, Eq, Not, And, Or, Impl, Iff, Forall, Exists, Box, Diamond),
        )
        if isinstance(node, Atom):
            arity = len(node.args)
            if arity > 0:
                predicates.append((node.symbol, arity))
            for arg in reversed(node.args):
                stack.append(("term", arg))
            continue
        if isinstance(node, Eq):
            has_equality = True
            stack.append(("term", node.right))
            stack.append(("term", node.left))
            continue
        if isinstance(node, Not):
            stack.append(("formula", node.formula))
            continue
        if isinstance(node, (And, Or, Impl, Iff)):
            stack.append(("formula", node.right))
            stack.append(("formula", node.left))
            continue
        if isinstance(node, (Forall, Exists)):
            stack.append(("formula", node.body))
            continue
        if isinstance(node, (Box, Diamond)):
            stack.append(("formula", node.body))
            if node.index is not None:
                stack.append(("term", node.index))

    if not has_equality:
        return [], [], False
    return _dedupe_keep_last(predicates), _dedupe_keep_last(functions), True


def _dedupe_keep_last(items: list[tuple[str, int]]) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    output: list[tuple[str, int]] = []
    for item in reversed(items):
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    output.reverse()
    return output


def _basic_equality_axioms() -> tuple[Formula, Formula, Formula]:
    x = Variable("EX")
    y = Variable("EY")
    z = Variable("EZ")
    reflexive = Forall(x, Eq(x, x))
    symmetric = Forall(x, Forall(y, Impl(Eq(x, y), Eq(y, x))))
    transitive = Forall(
        x,
        Forall(
            y,
            Forall(z, Impl(And(Eq(x, y), Eq(y, z)), Eq(x, z))),
        ),
    )
    return reflexive, symmetric, transitive


def _subst_pred_axioms(predicates: list[tuple[str, int]]) -> list[Formula]:
    axioms: list[Formula] = []
    for symbol, arity in predicates:
        left_vars, right_vars, quantified_vars, eq_chain = _subst_axiom_parts(
            arity,
            left_prefix="PX",
            right_prefix="PY",
        )
        p_left = Atom(symbol, tuple(left_vars))
        p_right = Atom(symbol, tuple(right_vars))
        body = Impl(And(eq_chain, p_left), p_right)
        axioms.append(_forall_all(quantified_vars, body))
    return axioms


def _subst_func_axioms(functions: list[tuple[str, int]]) -> list[Formula]:
    axioms: list[Formula] = []
    for symbol, arity in functions:
        left_vars, right_vars, quantified_vars, eq_chain = _subst_axiom_parts(
            arity,
            left_prefix="FX",
            right_prefix="FY",
        )
        f_left = Function(symbol, tuple(left_vars))
        f_right = Function(symbol, tuple(right_vars))
        body = Impl(eq_chain, Eq(f_left, f_right))
        axioms.append(_forall_all(quantified_vars, body))
    return axioms


def _subst_axiom_parts(
    arity: int,
    *,
    left_prefix: str,
    right_prefix: str,
) -> tuple[list[Variable], list[Variable], list[Variable], Formula]:
    left_vars = [Variable(f"{left_prefix}{i}") for i in range(arity)]
    right_vars = [Variable(f"{right_prefix}{i}") for i in range(arity)]
    quantified_vars: list[Variable] = []
    equalities: list[Formula] = []
    for left, right in zip(left_vars, right_vars, strict=True):
        quantified_vars.extend((left, right))
        equalities.append(Eq(left, right))
    return left_vars, right_vars, quantified_vars, combine_with_and(equalities)


def _forall_all(variables: Sequence[Variable], body: Formula) -> Formula:
    result = body
    for variable in reversed(variables):
        result = Forall(variable, result)
    return result


__all__ = ["add_equality_axioms"]
