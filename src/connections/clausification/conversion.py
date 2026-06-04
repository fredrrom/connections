from __future__ import annotations

from collections.abc import Iterable

from connections.core.formula import (
    And,
    Atom,
    Eq,
    Formula,
    Function,
    Not,
    Or,
    Prefixed,
    Prefix,
    Term,
    Variable,
)
from connections.core.matrix import Literal


def cnf_formula_to_literals(formula: Formula) -> tuple[Literal, ...]:
    if isinstance(formula, Or):
        return tuple(formula_to_literal(part) for part in flatten_or(formula))
    return (formula_to_literal(formula),)


def dnf(formula: Formula) -> Formula:
    if isinstance(formula, And) and isinstance(formula.left, Or):
        return Or(
            dnf(And(formula.left.left, formula.right)),
            dnf(And(formula.left.right, formula.right)),
        )
    if isinstance(formula, And) and isinstance(formula.right, Or):
        return Or(
            dnf(And(formula.left, formula.right.left)),
            dnf(And(formula.left, formula.right.right)),
        )
    if isinstance(formula, And):
        left = dnf(formula.left)
        right = dnf(formula.right)
        if isinstance(left, Or) or isinstance(right, Or):
            return dnf(And(left, right))
        return And(left, right)
    if isinstance(formula, Or):
        return Or(dnf(formula.left), dnf(formula.right))
    return formula


def mat(formula: Formula) -> list[list[Literal]]:
    if isinstance(formula, Or):
        clauses: list[list[Literal]] = []
        for part in flatten_or(formula):
            clauses.extend(mat(part))
        return clauses
    if isinstance(formula, And):
        left = _single_clause(formula.left)
        right = _single_clause(formula.right)
        if left is None or right is None:
            return []
        merged = _union2(left, right)
        return [] if merged is None else [merged]
    return [[formula_to_literal(formula)]]


def prefixed_dnf(expr: Formula) -> Formula:
    expr = _push_prefixed_compound(expr)
    if isinstance(expr, And):
        left_expr = _push_prefixed_compound(expr.left)
        right_expr = _push_prefixed_compound(expr.right)
        if isinstance(left_expr, Or):
            return Or(
                prefixed_dnf(And(left_expr.left, right_expr)),
                prefixed_dnf(And(left_expr.right, right_expr)),
            )
        if isinstance(right_expr, Or):
            return Or(
                prefixed_dnf(And(left_expr, right_expr.left)),
                prefixed_dnf(And(left_expr, right_expr.right)),
            )
        left = prefixed_dnf(left_expr)
        right = prefixed_dnf(right_expr)
        if isinstance(left, Or) or isinstance(right, Or):
            return prefixed_dnf(And(left, right))
        return And(left, right)
    if isinstance(expr, Or):
        return _or_from_parts(
            prefixed_dnf(part) for part in _flatten_prefixed_or(expr)
        )
    return expr


def prefixed_mat(expr: Formula) -> list[list[Literal]]:
    expr = _push_prefixed_compound(expr)
    if isinstance(expr, Or):
        clauses: list[list[Literal]] = []
        for part in _flatten_prefixed_or(expr):
            clauses.extend(prefixed_mat(part))
        return clauses
    if isinstance(expr, And):
        left = _prefixed_single_clause(expr.left)
        right = _prefixed_single_clause(expr.right)
        if left is None or right is None:
            return []
        merged = _union2(left, right)
        return [] if merged is None else [merged]
    return [[_prefixed_literal_to_literal(expr)]]


def formula_to_literal(formula: Formula) -> Literal:
    if isinstance(formula, Atom):
        return Literal(atom=formula, polarity=True)
    if isinstance(formula, Eq):
        return Literal(
            atom=Atom("equal___", (formula.left, formula.right)),
            polarity=True,
        )
    if isinstance(formula, Not) and isinstance(formula.formula, Atom):
        atom = formula.formula
        return Literal(atom=atom, polarity=False)
    if isinstance(formula, Not) and isinstance(formula.formula, Eq):
        eq = formula.formula
        return Literal(atom=Atom("equal___", (eq.left, eq.right)), polarity=False)
    raise ValueError(f"Expected literal formula, got {formula!r}")


def free_variables_for_literals(literals: tuple[Literal, ...]) -> tuple[Variable, ...]:
    variables: list[Variable] = []
    seen: set[Variable] = set()
    for literal in literals:
        for arg in literal.atom.args:
            for variable in _prefixed_variables_in_term(arg):
                if variable in seen:
                    continue
                seen.add(variable)
                variables.append(variable)
    return tuple(variables)


def is_literal(formula: Formula) -> bool:
    if isinstance(formula, Prefixed):
        return is_literal(formula.formula)
    return isinstance(formula, (Atom, Eq)) or (
        isinstance(formula, Not)
        and isinstance(_unwrap_prefixed(formula.formula), (Atom, Eq))
    )


def flatten_or(formula: Or) -> list[Formula]:
    parts: list[Formula] = []
    stack: list[Formula] = [formula]
    while stack:
        current = stack.pop()
        if isinstance(current, Or):
            stack.append(current.right)
            stack.append(current.left)
        else:
            parts.append(current)
    return parts


def _single_clause(formula: Formula) -> list[Literal] | None:
    clauses = mat(formula)
    if len(clauses) != 1:
        return None
    return clauses[0]


def _flatten_prefixed_or(expr: Or) -> list[Formula]:
    parts: list[Formula] = []
    stack: list[Formula] = [expr]
    while stack:
        current = _push_prefixed_compound(stack.pop())
        if isinstance(current, Or):
            stack.append(current.right)
            stack.append(current.left)
        else:
            parts.append(current)
    return parts


def _or_from_parts(parts: Iterable[Formula]) -> Formula:
    pending = list(parts)
    if not pending:
        raise ValueError("cannot build disjunction from no parts")
    while len(pending) > 1:
        next_pending: list[Formula] = []
        for index in range(0, len(pending), 2):
            try:
                right = pending[index + 1]
            except IndexError:
                next_pending.append(pending[index])
            else:
                next_pending.append(Or(pending[index], right))
        pending = next_pending
    return pending[0]


def _prefixed_single_clause(expr: Formula) -> list[Literal] | None:
    clauses = prefixed_mat(expr)
    if len(clauses) != 1:
        return None
    return clauses[0]


def _prefixed_literal_to_literal(formula: Formula) -> Literal:
    if isinstance(formula, Prefixed):
        return _prefixed_leaf_to_literal(formula.formula, formula.prefix)
    if isinstance(formula, Not) and isinstance(formula.formula, Prefixed):
        inner = formula.formula
        return _prefixed_leaf_to_literal(Not(inner.formula), inner.prefix)
    return formula_to_literal(formula)


def _prefixed_leaf_to_literal(formula: Formula, prefix: Prefix) -> Literal:
    if isinstance(formula, Atom):
        return Literal(
            atom=formula,
            prefix=prefix,
            polarity=True,
        )
    if isinstance(formula, Eq):
        return Literal(
            atom=Atom("equal___", (formula.left, formula.right)),
            prefix=prefix,
            polarity=True,
        )
    if isinstance(formula, Not) and isinstance(formula.formula, Atom):
        return Literal(
            atom=formula.formula,
            prefix=prefix,
            polarity=False,
        )
    if isinstance(formula, Not) and isinstance(formula.formula, Eq):
        eq = formula.formula
        return Literal(
            atom=Atom("equal___", (eq.left, eq.right)),
            prefix=prefix,
            polarity=False,
        )
    raise ValueError(f"Expected prefixed literal formula, got {formula!r}")


def _push_prefixed_compound(formula: Formula) -> Formula:
    if not isinstance(formula, Prefixed):
        return formula
    inner = formula.formula
    if isinstance(inner, And):
        return And(
            Prefixed(inner.left, formula.prefix),
            Prefixed(inner.right, formula.prefix),
        )
    if isinstance(inner, Or):
        return Or(
            Prefixed(inner.left, formula.prefix),
            Prefixed(inner.right, formula.prefix),
        )
    return formula


def _unwrap_prefixed(formula: Formula) -> Formula:
    if isinstance(formula, Prefixed):
        return formula.formula
    return formula


def _prefixed_variables_in_term(term: Term) -> tuple[Variable, ...]:
    if isinstance(term, Variable):
        return (term,) if term.prefix is not None else ()
    if isinstance(term, Function):
        variables: list[Variable] = []
        for arg in term.args:
            variables.extend(_prefixed_variables_in_term(arg))
        return tuple(variables)
    raise TypeError(f"Unsupported term node: {type(term)!r}")


def _complement(literal: Literal) -> Literal:
    polarity = not literal.polarity
    return Literal(atom=literal.atom, prefix=literal.prefix, polarity=polarity)


def _union2(left: list[Literal], right: list[Literal]) -> list[Literal] | None:
    seen = set(right)
    accepted: list[Literal] = []
    for literal in left:
        if literal in seen:
            continue
        complement = _complement(literal)
        if complement in seen:
            return None
        accepted.append(literal)
        seen.add(literal)
    return [*reversed(accepted), *right]


__all__ = [
    "cnf_formula_to_literals",
    "dnf",
    "flatten_or",
    "formula_to_literal",
    "free_variables_for_literals",
    "is_literal",
    "mat",
    "prefixed_dnf",
    "prefixed_mat",
]
