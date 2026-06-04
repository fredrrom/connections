from __future__ import annotations

from typing import Any

from connections.constraints.term_types import (
    LiteralCacheEntry,
    ResolveCacheEntry,
    ScopedTerm as _ScopedTerm,
    TableauVariable,
    TableauVariableKey,
    TermBinding,
    TermReference,
    TermSubstitutionInputTerm,
    TermSubstitutionLiteral,
    TermSubstitutionTerm,
    TermSubstitutionVariable,
)
from connections.constraints.term_resolution import (
    bindings_to_dict as _bindings_to_dict,
    equal_term_refs as _equal_term_refs,
    occurs_check as _occurs_check,
    resolve as _resolve,
    substitute_literal as _substitute_literal,
    substitute_term as _substitute_term,
    substitute_term_with_pending as _substitute_term_with_pending,
    variable_key as _variable_key,
)
from connections.constraints.term_unification import (
    atom_value as _atom_value,
    is_atom as _is_atom,
    is_function as _is_function,
    is_variable as _is_variable,
    scoped_unifiable_from_empty as _scoped_unifiable_from_empty,
)
from connections.constraints.term_unifier import unify_terms


class TermSubstitution:
    def __init__(self):
        self.bindings: dict[TermSubstitutionVariable, TermReference] = {}
        self._binding_owner_app_ids: dict[TermSubstitutionVariable, int | None] = {}
        self._variables_by_owner_app_id: dict[
            int | None, set[TermSubstitutionVariable]
        ] = {}
        self.revision = 0
        self._resolve_cache: dict[TermSubstitutionVariable, ResolveCacheEntry] = {}
        self._term_cache: dict[tuple[Any, int | None], ResolveCacheEntry] = {}
        self._literal_cache: dict[
            tuple[TermSubstitutionLiteral, int | None], LiteralCacheEntry
        ] = {}

    @staticmethod
    def unifiable_from_empty(
        *,
        older: TermSubstitutionLiteral | TermSubstitutionInputTerm,
        newer: TermSubstitutionLiteral | TermSubstitutionInputTerm,
    ) -> bool:
        older_value = _atom_value(older)
        newer_value = _atom_value(newer)
        if (
            _is_atom(older_value)
            and _is_atom(newer_value)
            and older_value.symbol == newer_value.symbol
            and len(older_value.args) == len(newer_value.args)
        ):
            equations: list[tuple[_ScopedTerm, _ScopedTerm]] = [
                ((0, older_arg), (1, newer_arg))
                for older_arg, newer_arg in zip(older_value.args, newer_value.args)
            ]
        else:
            equations = [
                ((0, older_value), (1, newer_value)),
            ]
        return _scoped_unifiable_from_empty(equations)

    def unify(
        self,
        *,
        older: TermSubstitutionLiteral | TermSubstitutionInputTerm,
        newer: TermSubstitutionLiteral | TermSubstitutionInputTerm,
    ) -> tuple[bool, tuple[TermBinding, ...]]:
        return unify_terms(
            self.bindings,
            older=older,
            older_instance=None,
            newer=newer,
            newer_instance=None,
        )

    def unify_literals(
        self,
        *,
        older: TermSubstitutionLiteral,
        older_instance: int | None,
        newer: TermSubstitutionLiteral,
        newer_instance: int | None,
    ) -> tuple[bool, tuple[TermBinding, ...]]:
        return unify_terms(
            self.bindings,
            older=older,
            older_instance=older_instance,
            newer=newer,
            newer_instance=newer_instance,
        )

    def bind(
        self,
        bindings: list[TermBinding] | tuple[TermBinding, ...],
        *,
        owner_app_id: int | None = None,
    ) -> None:
        if not bindings:
            return
        self._validate_bindings(bindings)
        owner_variables = self._variables_by_owner_app_id.setdefault(
            owner_app_id,
            set(),
        )
        for variable, term in bindings:
            self.bindings[variable] = term
            self._binding_owner_app_ids[variable] = owner_app_id
            owner_variables.add(variable)
        self.revision += 1

    def _validate_bindings(
        self, bindings: list[TermBinding] | tuple[TermBinding, ...]
    ) -> None:
        seen: set[TermSubstitutionVariable] = set()
        for variable, term in bindings:
            target, target_instance = term
            if variable in seen:
                raise ValueError("binding batch cannot bind the same variable twice")
            if variable in self.bindings:
                raise ValueError("variable is already bound")
            if _is_variable(target):
                if _variable_key(target, target_instance) == variable:
                    raise ValueError("variable cannot bind to itself")
            elif not _is_function(target):
                raise TypeError("binding target must be a term")
            seen.add(variable)

    def unbind(self, bindings: list[TermBinding] | tuple[TermBinding, ...]) -> None:
        if not bindings:
            return
        for variable, _ in reversed(bindings):
            if variable not in self.bindings:
                raise ValueError("cannot remove a binding that is not present")
        for variable, term in reversed(bindings):
            if self.bindings[variable] != term:
                raise ValueError("cannot remove a binding with a different target")
        for variable, _ in reversed(bindings):
            del self.bindings[variable]
            owner_app_id = self._binding_owner_app_ids.pop(variable)
            owner_variables = self._variables_by_owner_app_id[owner_app_id]
            owner_variables.remove(variable)
            if not owner_variables:
                del self._variables_by_owner_app_id[owner_app_id]
        self.revision += 1

    def unbind_owned_by(self, owner_app_ids: tuple[int, ...] | set[int]) -> None:
        if not owner_app_ids:
            return
        variables = tuple(
            variable
            for owner_app_id in owner_app_ids
            for variable in self._variables_by_owner_app_id.get(owner_app_id, ())
        )
        bindings = tuple((variable, self.bindings[variable]) for variable in variables)
        self.unbind(bindings)

    def occurs_check(
        self,
        var: TermSubstitutionVariable,
        term: Any,
        pending_bindings: dict[TermSubstitutionVariable, TermReference] | None = None,
        *,
        instance_id: int | None = None,
    ) -> bool:
        return _occurs_check(
            self.bindings,
            var,
            term,
            pending_bindings=pending_bindings,
            instance_id=instance_id,
        )

    def equal(
        self, left: TermSubstitutionLiteral, right: TermSubstitutionLiteral
    ) -> bool:
        return self.equal_literals(
            left,
            left_instance=None,
            right=right,
            right_instance=None,
        )

    def equal_literals(
        self,
        left: TermSubstitutionLiteral,
        *,
        left_instance: int | None,
        right: TermSubstitutionLiteral,
        right_instance: int | None,
    ) -> bool:
        return left.polarity == right.polarity and _equal_term_refs(
            self.bindings,
            left.atom,
            left_instance,
            right.atom,
            right_instance,
        )

    def complementary(
        self, left: TermSubstitutionLiteral, right: TermSubstitutionLiteral
    ) -> bool:
        return self.complementary_literals(
            left,
            left_instance=None,
            right=right,
            right_instance=None,
        )

    def complementary_literals(
        self,
        left: TermSubstitutionLiteral,
        *,
        left_instance: int | None,
        right: TermSubstitutionLiteral,
        right_instance: int | None,
    ) -> bool:
        return left.polarity != right.polarity and _equal_term_refs(
            self.bindings,
            left.atom,
            left_instance,
            right.atom,
            right_instance,
        )

    def __call__(
        self, value: TermSubstitutionLiteral, *, instance_id: int | None = None
    ) -> TermSubstitutionLiteral:
        cache_key = (value, instance_id)
        cached = self._literal_cache.get(cache_key)
        if cached is not None and cached.revision == self.revision:
            return cached.resolved
        resolved = _substitute_literal(self, value, instance_id=instance_id)
        self._literal_cache[cache_key] = LiteralCacheEntry(self.revision, resolved)
        return resolved

    def substitute_term(
        self,
        term: TermSubstitutionInputTerm,
        *,
        instance_id: int | None = None,
        pending_bindings: tuple[TermBinding, ...] = (),
    ) -> TermSubstitutionTerm:
        if not pending_bindings:
            return _substitute_term(self, term, instance_id=instance_id)
        return _substitute_term_with_pending(
            self,
            term,
            instance_id=instance_id,
            pending_bindings=dict(pending_bindings),
        )

    def to_dict(self) -> dict[TermSubstitutionVariable, TermSubstitutionTerm]:
        return _bindings_to_dict(self)

    def _resolve(
        self,
        item: Any,
        pending_bindings: dict[TermSubstitutionVariable, TermReference] | None = None,
    ) -> Any:
        return _resolve(self, item, pending_bindings)

    def __repr__(self) -> str:
        return repr(self.to_dict())


__all__ = [
    "TermBinding",
    "TermSubstitution",
    "TermSubstitutionTerm",
    "TermSubstitutionVariable",
    "TableauVariable",
    "TableauVariableKey",
    "TermReference",
]
