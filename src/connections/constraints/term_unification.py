from __future__ import annotations

from typing import Any, TypeGuard, cast

from connections.core.formula import Atom, Function, Prefix, Term, Variable
from connections.core.matrix import Literal
from connections.constraints.term_types import (
    ScopedTerm,
    ScopedVariable,
    TableauVariable,
    TableauVariableKey,
    TermReference,
    TermSubstitutionAtom,
    TermSubstitutionInputTerm,
    TermSubstitutionLiteral,
    TermSubstitutionTerm,
    TermSubstitutionVariable,
)


def atom_value(
    item: TermSubstitutionLiteral | TermSubstitutionInputTerm | TermSubstitutionAtom,
) -> TermSubstitutionInputTerm | TermSubstitutionAtom:
    if type(item) is Literal:
        return item.atom
    return cast(TermSubstitutionInputTerm | TermSubstitutionAtom, item)


def term_ref(term: Any, instance_id: int | None) -> TermReference:
    if type(term) is tuple:
        variable_instance_id, source = term
        return source, variable_instance_id
    return term, instance_id


def is_variable(item: object) -> TypeGuard[TermSubstitutionVariable]:
    item_type = type(item)
    if item_type is Variable:
        return cast(Variable, item).prefix is None
    if item_type is not tuple:
        return False
    item_tuple = cast(tuple[object, ...], item)
    return (
        len(item_tuple) == 2
        and type(item_tuple[0]) is int
        and type(item_tuple[1]) is Variable
        and item_tuple[1].prefix is None
    )


def is_tableau_variable_key(item: object) -> TypeGuard[TableauVariableKey]:
    return (
        type(item) is tuple
        and len(item) == 2
        and type(item[0]) is int
        and type(item[1]) is Variable
    )


def is_function(item: object) -> TypeGuard[Function]:
    return type(item) is Function


def is_atom(item: object) -> TypeGuard[Atom]:
    return type(item) is Atom


def is_literal(item: object) -> TypeGuard[Literal]:
    return type(item) is Literal


def is_ground(item: Any) -> bool:
    item_type = type(item)
    if item_type is Variable:
        return False
    if item_type is tuple and len(item) == 2 and type(item[0]) is int:
        return False
    if item_type is Function or item_type is Atom:
        return item.is_ground
    return item.is_ground


def same_structure(left: Any, right: Any) -> bool:
    left = unification_view(left)
    right = unification_view(right)
    left_type = type(left)
    right_type = type(right)
    if left_type is Atom:
        return (
            right_type is Atom
            and left.symbol == right.symbol
            and len(left.args) == len(right.args)
        )
    if left_type is Function:
        return (
            right_type is Function
            and left.symbol == right.symbol
            and len(left.args) == len(right.args)
        )
    return False


def unification_view(item: Any) -> Any:
    if type(item) is Variable and item.prefix is not None:
        return Function(
            "$prefixed",
            (
                Variable(item.symbol, vid=item.vid),
                _prefix_as_function(item.prefix),
            ),
        )
    if type(item) is Function and item.prefix is not None:
        return Function(
            "$prefixed",
            (
                Function(item.symbol, item.args),
                _prefix_as_function(item.prefix),
            ),
        )
    return item


def prefix_display_term(term: TermSubstitutionTerm) -> Term:
    if isinstance(term, TableauVariable):
        return Variable(
            f"{term.source.symbol}@{term.instance_id}",
            prefix=term.source.prefix,
            vid=term.source.vid,
        )
    if type(term) is Variable:
        return term
    if type(term) is Function:
        return Function(
            term.symbol,
            tuple(prefix_display_term(arg) for arg in term.args),
            term.prefix,
        )
    raise TypeError(f"unsupported term: {term!r}")


def scoped_unifiable_from_empty(
    equations: list[tuple[ScopedTerm, ScopedTerm]],
) -> bool:
    pending_bindings: dict[ScopedVariable, ScopedTerm] = {}
    while equations:
        older_term, newer_term = equations.pop()
        if older_term == newer_term:
            continue

        older_resolved = (
            _scoped_resolve(older_term, pending_bindings)
            if is_variable(older_term[1])
            else older_term
        )
        newer_resolved = (
            _scoped_resolve(newer_term, pending_bindings)
            if is_variable(newer_term[1])
            else newer_term
        )
        if older_resolved == newer_resolved:
            continue

        newer_side, newer_value = newer_term
        if is_variable(newer_value):
            newer_key: ScopedVariable = (newer_side, newer_value)
            newer_target = pending_bindings.get(newer_key)
            if newer_target is None:
                if _scoped_occurs(newer_key, older_term, pending_bindings):
                    return False
                pending_bindings[newer_key] = older_term
                continue
            equations.append((older_term, newer_target))
            continue

        older_side, older_value = older_term
        if is_variable(older_value):
            older_key: ScopedVariable = (older_side, older_value)
            older_target = pending_bindings.get(older_key)
            if older_target is not None:
                equations.append((older_target, newer_term))
                continue
            if _scoped_occurs(older_key, newer_term, pending_bindings):
                return False
            pending_bindings[older_key] = newer_term
            continue

        older_view = _scoped_unification_view(older_resolved)
        newer_view = _scoped_unification_view(newer_resolved)
        if not _same_scoped_structure(older_view, newer_view):
            return False
        older_side, older_value = older_view
        newer_side, newer_value = newer_view
        older_struct = cast(Atom | Function, older_value)
        newer_struct = cast(Atom | Function, newer_value)
        equations.extend(
            ((older_side, older_arg), (newer_side, newer_arg))
            for older_arg, newer_arg in zip(older_struct.args, newer_struct.args)
        )
    return True


def _prefix_as_function(prefix: Prefix) -> Function:
    return Function("$prefix", prefix.parts)


def _scoped_resolve(
    item: ScopedTerm,
    pending_bindings: dict[ScopedVariable, ScopedTerm],
) -> ScopedTerm:
    side, value = item
    while is_variable(value):
        key: ScopedVariable = (side, value)
        target = pending_bindings.get(key)
        if target is None:
            return side, value
        side, value = target
    return side, value


def _scoped_occurs(
    variable: ScopedVariable,
    term: ScopedTerm,
    pending_bindings: dict[ScopedVariable, ScopedTerm],
) -> bool:
    side, value = (
        _scoped_resolve(term, pending_bindings) if is_variable(term[1]) else term
    )
    if is_variable(value):
        return (side, value) == variable
    side, value = _scoped_unification_view((side, value))
    if is_atom(value) or is_function(value):
        return any(
            _scoped_occurs(variable, (side, arg), pending_bindings)
            for arg in value.args
        )
    return False


def _same_scoped_structure(left: ScopedTerm, right: ScopedTerm) -> bool:
    left = _scoped_unification_view(left)
    right = _scoped_unification_view(right)
    _, left_value = left
    _, right_value = right
    return same_structure(left_value, right_value)


def _scoped_unification_view(item: ScopedTerm) -> ScopedTerm:
    side, value = item
    return side, unification_view(value)


__all__ = [
    "atom_value",
    "is_atom",
    "is_function",
    "is_ground",
    "is_literal",
    "is_tableau_variable_key",
    "is_variable",
    "prefix_display_term",
    "same_structure",
    "scoped_unifiable_from_empty",
    "term_ref",
    "unification_view",
]
