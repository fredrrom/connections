from __future__ import annotations

from typing import Any, cast

from connections.core.formula import Atom, Function
from connections.constraints.term_resolution import (
    occurs_check,
    resolve_ref,
    same_term_ref,
    variable_key,
)
from connections.constraints.term_types import (
    TermBinding,
    TermReference,
    TermSubstitutionInputTerm,
    TermSubstitutionLiteral,
    TermSubstitutionVariable,
)
from connections.constraints.term_unification import (
    atom_value,
    is_atom,
    is_ground,
    is_variable,
    same_structure,
    term_ref,
    unification_view,
)


def unify_terms(
    bindings: dict[TermSubstitutionVariable, TermReference],
    *,
    older: TermSubstitutionLiteral | TermSubstitutionInputTerm,
    older_instance: int | None,
    newer: TermSubstitutionLiteral | TermSubstitutionInputTerm,
    newer_instance: int | None,
) -> tuple[bool, tuple[TermBinding, ...]]:
    older_value = atom_value(older)
    newer_value = atom_value(newer)
    if (
        is_atom(older_value)
        and is_atom(newer_value)
        and older_value.symbol == newer_value.symbol
        and len(older_value.args) == len(newer_value.args)
    ):
        equations: list[tuple[Any, int | None, Any, int | None]] = [
            (older_arg, older_instance, newer_arg, newer_instance)
            for older_arg, newer_arg in zip(older_value.args, newer_value.args)
        ]
    else:
        equations = [(older_value, older_instance, newer_value, newer_instance)]

    pending_bindings: dict[TermSubstitutionVariable, TermReference] = {}

    while equations:
        older_term, older_inst, newer_term, newer_inst = equations.pop()
        if same_term_ref(older_term, older_inst, newer_term, newer_inst):
            continue

        older_resolved, older_resolved_inst = resolve_ref(
            bindings,
            older_term,
            older_inst,
            pending_bindings,
        )
        newer_resolved, newer_resolved_inst = resolve_ref(
            bindings,
            newer_term,
            newer_inst,
            pending_bindings,
        )
        if same_term_ref(
            older_resolved,
            older_resolved_inst,
            newer_resolved,
            newer_resolved_inst,
        ):
            continue

        if is_variable(newer_term):
            newer_key = variable_key(newer_term, newer_inst)
            newer_target = pending_bindings.get(newer_key)
            if newer_target is None:
                newer_target = bindings.get(newer_key)
            if newer_target is None:
                if (
                    not is_variable(older_resolved)
                    and not is_ground(older_resolved)
                    and occurs_check(
                        bindings,
                        newer_key,
                        older_resolved,
                        instance_id=older_resolved_inst,
                        pending_bindings=pending_bindings,
                    )
                ):
                    return False, ()
                pending_bindings[newer_key] = term_ref(older_term, older_inst)
                continue
            equations.append(
                (older_term, older_inst, newer_target[0], newer_target[1])
            )
            continue

        if is_variable(older_term):
            older_key = variable_key(older_term, older_inst)
            older_target = pending_bindings.get(older_key)
            if older_target is None:
                older_target = bindings.get(older_key)
            if older_target is not None:
                equations.append(
                    (older_target[0], older_target[1], newer_term, newer_inst)
                )
                continue
            if (
                not is_variable(newer_resolved)
                and not is_ground(newer_resolved)
                and occurs_check(
                    bindings,
                    older_key,
                    newer_resolved,
                    instance_id=newer_resolved_inst,
                    pending_bindings=pending_bindings,
                )
            ):
                return False, ()
            pending_bindings[older_key] = term_ref(newer_term, newer_inst)
            continue

        older_view = unification_view(older_resolved)
        newer_view = unification_view(newer_resolved)
        if not same_structure(older_view, newer_view):
            return False, ()

        older_struct = cast(Atom | Function, older_view)
        newer_struct = cast(Atom | Function, newer_view)
        equations.extend(
            (older_arg, older_resolved_inst, newer_arg, newer_resolved_inst)
            for older_arg, newer_arg in zip(older_struct.args, newer_struct.args)
        )

    return True, tuple(pending_bindings.items())


__all__ = ["unify_terms"]
