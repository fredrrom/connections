from __future__ import annotations

from typing import Any, Protocol, cast

from connections.syntax.formula import Atom, Function, Prefix, Term, Variable
from connections.syntax.matrix import Literal
from connections.constraints.term_types import (
    LiteralCacheEntry,
    ResolveCacheEntry,
    TableauVariable,
    TermRef,
    TermReference,
    TermSubstitutionInputTerm,
    TermSubstitutionLiteral,
    TermSubstitutionTerm,
    TermSubstitutionVariable,
)
from connections.constraints.term_unification import (
    is_atom,
    is_function,
    is_ground,
    is_tableau_variable_key,
    is_variable,
    prefix_display_term,
    same_structure,
    unification_view,
)


class TermSubstitutionState(Protocol):
    bindings: dict[TermSubstitutionVariable, TermReference]
    revision: int
    _resolve_cache: dict[TermSubstitutionVariable, ResolveCacheEntry]
    _term_cache: dict[tuple[Any, int | None], ResolveCacheEntry]
    _literal_cache: dict[tuple[TermSubstitutionLiteral, int | None], LiteralCacheEntry]


def resolve(
    state: TermSubstitutionState,
    item: Any,
    pending_bindings: dict[TermSubstitutionVariable, TermReference] | None = None,
) -> Any:
    if pending_bindings is None and is_variable(item):
        variable = variable_key(item, None)
        cached = state._resolve_cache.get(variable)
        if cached is not None and cached.revision == state.revision:
            return cached.resolved
        resolved, _ = resolve_ref(state.bindings, item, None, {})
        state._resolve_cache[variable] = ResolveCacheEntry(state.revision, resolved)
        return resolved
    resolved, _ = resolve_ref(state.bindings, item, None, pending_bindings or {})
    return resolved


def resolve_ref(
    bindings: dict[TermSubstitutionVariable, TermReference],
    item: Any,
    instance_id: int | None,
    pending_bindings: dict[TermSubstitutionVariable, TermReference],
) -> TermRef:
    current = item
    current_instance = instance_id
    while is_variable(current):
        variable = variable_key(current, current_instance)
        target = pending_bindings.get(variable)
        if target is None:
            target = bindings.get(variable)
            if target is None:
                return current, current_instance
        current, current_instance = target
    return current, current_instance


def occurs_check(
    bindings: dict[TermSubstitutionVariable, TermReference],
    var: TermSubstitutionVariable,
    term: Any,
    pending_bindings: dict[TermSubstitutionVariable, TermReference] | None = None,
    *,
    instance_id: int | None = None,
) -> bool:
    pending = {} if pending_bindings is None else pending_bindings
    stack: list[TermRef] = [(term, instance_id)]
    while stack:
        current, current_instance = stack.pop()
        current, current_instance = resolve_ref(
            bindings,
            current,
            current_instance,
            pending,
        )
        if is_variable(current):
            if variable_key(current, current_instance) == var:
                return True
            continue
        current_view = unification_view(current)
        if (
            (is_atom(current_view) or is_function(current_view))
            and not is_ground(current_view)
        ):
            stack.extend((arg, current_instance) for arg in current_view.args)
    return False


def equal_term_refs(
    bindings: dict[TermSubstitutionVariable, TermReference],
    left: Any,
    left_instance: int | None,
    right: Any,
    right_instance: int | None,
) -> bool:
    stack: list[tuple[Any, int | None, Any, int | None]] = [
        (left, left_instance, right, right_instance)
    ]
    while stack:
        left_term, left_inst, right_term, right_inst = stack.pop()
        if same_term_ref(left_term, left_inst, right_term, right_inst):
            continue
        left_term, left_inst = resolve_ref(bindings, left_term, left_inst, {})
        right_term, right_inst = resolve_ref(bindings, right_term, right_inst, {})
        if same_term_ref(left_term, left_inst, right_term, right_inst):
            continue
        if is_variable(left_term) or is_variable(right_term):
            return False
        left_view = unification_view(left_term)
        right_view = unification_view(right_term)
        if not same_structure(left_view, right_view):
            return False
        left_struct = cast(Atom | Function, left_view)
        right_struct = cast(Atom | Function, right_view)
        stack.extend(
            (left_arg, left_inst, right_arg, right_inst)
            for left_arg, right_arg in zip(left_struct.args, right_struct.args)
        )
    return True


def same_term_ref(
    left: Any,
    left_instance: int | None,
    right: Any,
    right_instance: int | None,
) -> bool:
    if is_variable(left) and is_variable(right):
        return variable_key(left, left_instance) == variable_key(
            right,
            right_instance,
        )
    if left_instance != right_instance and not (is_ground(left) and is_ground(right)):
        return False
    return left == right


def variable_key(
    variable: TermSubstitutionVariable,
    instance_id: int | None,
) -> TermSubstitutionVariable:
    if type(variable) is tuple:
        return variable
    source = cast(Variable, variable)
    if instance_id is None:
        return source
    return instance_id, source


def substitute_literal(
    state: TermSubstitutionState,
    literal: TermSubstitutionLiteral,
    *,
    instance_id: int | None,
) -> Literal:
    return Literal(
        atom=Atom(
            literal.atom.symbol,
            cast(
                tuple[Term, ...],
                tuple(
                    substitute_term(state, arg, instance_id=instance_id)
                    for arg in literal.atom.args
                ),
            ),
        ),
        prefix=literal.prefix,
        polarity=literal.polarity,
    )


def substitute_term(
    state: TermSubstitutionState,
    term: TermSubstitutionInputTerm,
    *,
    instance_id: int | None,
) -> TermSubstitutionTerm:
    if is_function(term) and term.is_ground:
        return term
    cache_key = (term, instance_id)
    cached = state._term_cache.get(cache_key)
    if cached is not None and cached.revision == state.revision:
        return cached.resolved
    resolved, resolved_instance = resolve_ref(state.bindings, term, instance_id, {})
    if is_variable(resolved):
        substituted = display_variable(variable_key(resolved, resolved_instance))
    elif type(resolved) is Variable:
        substituted = Variable(
            resolved.symbol,
            prefix=_substitute_prefix(
                state,
                resolved.prefix,
                instance_id=resolved_instance,
            ),
            vid=resolved.vid,
        )
    else:
        substituted = Function(
            cast(Function, resolved).symbol,
            cast(
                tuple[Term, ...],
                tuple(
                    substitute_term(state, arg, instance_id=resolved_instance)
                    for arg in cast(Function, resolved).args
                ),
            ),
            cast(Function, resolved).prefix,
        )
    state._term_cache[cache_key] = ResolveCacheEntry(state.revision, substituted)
    return substituted


def substitute_term_with_pending(
    state: TermSubstitutionState,
    term: TermSubstitutionInputTerm,
    *,
    instance_id: int | None,
    pending_bindings: dict[TermSubstitutionVariable, TermReference],
) -> TermSubstitutionTerm:
    resolved, resolved_instance = resolve_ref(
        state.bindings,
        term,
        instance_id,
        pending_bindings,
    )
    if is_variable(resolved):
        return display_variable(variable_key(resolved, resolved_instance))
    if type(resolved) is Variable:
        return Variable(
            resolved.symbol,
            prefix=_substitute_prefix_with_pending(
                state,
                resolved.prefix,
                instance_id=resolved_instance,
                pending_bindings=pending_bindings,
            ),
            vid=resolved.vid,
        )
    return Function(
        cast(Function, resolved).symbol,
        cast(
            tuple[Term, ...],
            tuple(
                substitute_term_with_pending(
                    state,
                    arg,
                    instance_id=resolved_instance,
                    pending_bindings=pending_bindings,
                )
                for arg in cast(Function, resolved).args
            ),
        ),
        cast(Function, resolved).prefix,
    )


def bindings_to_dict(
    state: TermSubstitutionState,
) -> dict[TermSubstitutionVariable, TermSubstitutionTerm]:
    return {
        variable: substitute_term(state, variable, instance_id=None)
        for variable in state.bindings
    }


def display_variable(variable: TermSubstitutionVariable) -> TermSubstitutionTerm:
    if is_tableau_variable_key(variable):
        instance_id, source = variable
        return TableauVariable(instance_id=instance_id, source=source)
    return cast(Variable, variable)


def _substitute_prefix(
    state: TermSubstitutionState,
    prefix: Prefix | None,
    *,
    instance_id: int | None,
):
    if prefix is None:
        return None
    return type(prefix)(
        tuple(
            prefix_display_term(substitute_term(state, part, instance_id=instance_id))
            for part in prefix.parts
        )
    )


def _substitute_prefix_with_pending(
    state: TermSubstitutionState,
    prefix: Prefix | None,
    *,
    instance_id: int | None,
    pending_bindings: dict[TermSubstitutionVariable, TermReference],
):
    if prefix is None:
        return None
    return type(prefix)(
        tuple(
            prefix_display_term(
                substitute_term_with_pending(
                    state,
                    part,
                    instance_id=instance_id,
                    pending_bindings=pending_bindings,
                )
            )
            for part in prefix.parts
        )
    )


__all__ = [
    "bindings_to_dict",
    "display_variable",
    "equal_term_refs",
    "occurs_check",
    "resolve",
    "resolve_ref",
    "same_term_ref",
    "substitute_literal",
    "substitute_term",
    "substitute_term_with_pending",
    "variable_key",
]
