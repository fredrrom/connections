from __future__ import annotations

from typing import Any

from connections.syntax.formula import Function, Prefix, Term, Variable
from connections.syntax.matrix import Literal
from connections.constraints.delta import (
    ConstraintDelta,
    FreeVariableReference,
    prefix_delta,
)
from connections.constraints.prefix import (
    PrefixConstraintStore,
    PrefixEquation,
    free_variables_admissible as _free_variables_admissible,
)
from connections.constraints.term import (
    TableauVariable,
    TermBinding,
    TermSubstitution,
    TermSubstitutionTerm,
)

_CLASSICAL_LOGICS = {"classical"}
_INTUITIONISTIC_LOGICS = {"intuitionistic", "intu"}


class ConstraintStore:
    def __init__(self) -> None:
        self.terms = TermSubstitution()
        self.prefixes = PrefixConstraintStore()
        self._free_variables: list[FreeVariableReference] = []
        self._free_variable_owner_app_ids: list[int | None] = []
        self._free_variable_revision = 0

    @property
    def revision(self) -> int:
        return (
            self.terms.revision + self.prefixes.revision + self._free_variable_revision
        )

    @property
    def term_bindings(self) -> dict[Any, tuple[Any, int | None]]:
        return self.terms.bindings

    @property
    def prefix_equations(self) -> tuple[PrefixEquation, ...]:
        return self.prefixes.equations

    @property
    def free_variables(self) -> tuple[FreeVariableReference, ...]:
        return tuple(self._free_variables)

    def delta_for_literals(
        self,
        *,
        older: Literal,
        older_instance: int | None,
        newer: Literal,
        newer_instance: int | None,
        logic: str = "classical",
        domain: str = "constant",
        free_variables: tuple[FreeVariableReference, ...] = (),
    ) -> ConstraintDelta | None:
        unifies, bindings = self.terms.unify_literals(
            older=older,
            older_instance=older_instance,
            newer=newer,
            newer_instance=newer_instance,
        )
        if not unifies:
            return None
        if logic.lower() in _CLASSICAL_LOGICS:
            return ConstraintDelta(
                term_bindings=bindings,
                free_variables=free_variables,
            )
        prefix_equations = self._prefix_equations_for_literals(
            older,
            older_instance=older_instance,
            newer=newer,
            newer_instance=newer_instance,
            logic=logic,
            domain=domain,
            pending_bindings=bindings,
        )
        if prefix_equations is None:
            return None
        if not self.free_variable_refs_admissible(
            free_variables,
            logic=logic,
            domain=domain,
            pending_bindings=bindings,
        ):
            return None
        return ConstraintDelta(
            term_bindings=bindings,
            prefix_equations=prefix_equations,
            free_variables=free_variables,
        )

    def delta_for_free_variables(
        self,
        free_variables: tuple[FreeVariableReference, ...],
        *,
        logic: str,
        domain: str,
    ) -> ConstraintDelta | None:
        if not self.free_variable_refs_admissible(
            free_variables,
            logic=logic,
            domain=domain,
        ):
            return None
        return ConstraintDelta(free_variables=free_variables)

    def free_variable_refs_admissible(
        self,
        free_variables: tuple[FreeVariableReference, ...] = (),
        *,
        logic: str,
        domain: str,
        pending_bindings: tuple[TermBinding, ...] = (),
    ) -> bool:
        if logic.lower() in _CLASSICAL_LOGICS:
            return True
        refs = (*self.free_variables, *free_variables)
        if not refs:
            return True
        variables, resolved_terms = self._free_variable_admissibility_inputs(
            refs,
            pending_bindings=pending_bindings,
        )
        return _free_variables_admissible(
            variables,
            logic=logic,
            domain=domain,
            resolved_terms=resolved_terms,
        )

    def delta_for_prefixes(
        self,
        older: Prefix | None,
        newer: Prefix | None,
        *,
        older_instance: int | None = None,
        newer_instance: int | None = None,
        logic: str,
        domain: str,
    ) -> ConstraintDelta | None:
        equations = self._prefix_equations_for(
            older,
            older_instance,
            newer,
            newer_instance,
            logic=logic,
            domain=domain,
        )
        return None if equations is None else prefix_delta(equations)

    def satisfied_literals(
        self,
        left: Literal,
        *,
        left_instance: int | None,
        right: Literal,
        right_instance: int | None,
        logic: str = "classical",
        domain: str = "constant",
    ) -> bool:
        if not self.terms.equal_literals(
            left,
            left_instance=left_instance,
            right=right,
            right_instance=right_instance,
        ):
            return False
        if logic.lower() in _CLASSICAL_LOGICS:
            return True
        return self._prefixes_satisfied(
            left.prefix,
            left_instance,
            right.prefix,
            right_instance,
            logic=logic,
            domain=domain,
        )

    def satisfiable(self, *, logic: str, domain: str) -> bool:
        return self.prefixes.satisfiable(
            logic=logic,
            domain=domain,
        ) and self.free_variable_refs_admissible(
            logic=logic,
            domain=domain,
        )

    def commit(
        self,
        delta: ConstraintDelta,
        *,
        owner_app_id: int | None = None,
    ) -> None:
        if delta.term_bindings:
            self.terms.bind(delta.term_bindings, owner_app_id=owner_app_id)
        if delta.prefix_equations:
            self.prefixes.commit(delta.prefix_equations, owner_app_id=owner_app_id)
        if delta.free_variables:
            self._free_variables.extend(delta.free_variables)
            self._free_variable_owner_app_ids.extend(
                owner_app_id for _ in delta.free_variables
            )
            self._free_variable_revision += 1

    def rollback_owned_by(self, owner_app_ids: tuple[int, ...] | set[int]) -> None:
        self.terms.unbind_owned_by(owner_app_ids)
        self.prefixes.rollback_owned_by(owner_app_ids)
        self._rollback_free_variables_owned_by(owner_app_ids)

    def _rollback_free_variables_owned_by(
        self, owner_app_ids: tuple[int, ...] | set[int]
    ) -> None:
        if not owner_app_ids:
            return
        owner_id_set = set(owner_app_ids)
        kept = [
            (free_variable, owner_app_id)
            for free_variable, owner_app_id in zip(
                self._free_variables,
                self._free_variable_owner_app_ids,
                strict=True,
            )
            if owner_app_id not in owner_id_set
        ]
        if len(kept) == len(self._free_variables):
            return
        self._free_variables = [free_variable for free_variable, _ in kept]
        self._free_variable_owner_app_ids = [owner_app_id for _, owner_app_id in kept]
        self._free_variable_revision += 1

    def _prefix_equations_for(
        self,
        older: Prefix | None,
        older_instance: int | None,
        newer: Prefix | None,
        newer_instance: int | None,
        *,
        logic: str,
        domain: str,
        pending_bindings: tuple[TermBinding, ...] = (),
    ) -> tuple[PrefixEquation, ...] | None:
        if logic.lower() in _CLASSICAL_LOGICS:
            return ()
        older_prefix = self._substituted_prefix(
            _literal_prefix(older),
            older_instance,
            pending_bindings=pending_bindings,
        )
        newer_prefix = self._substituted_prefix(
            _literal_prefix(newer),
            newer_instance,
            pending_bindings=pending_bindings,
        )
        return self.prefixes.delta_for(
            older_prefix,
            None,
            newer_prefix,
            None,
            logic=logic,
            domain=domain,
        )

    def _prefix_equations_for_literals(
        self,
        older: Literal,
        *,
        older_instance: int | None,
        newer: Literal,
        newer_instance: int | None,
        logic: str,
        domain: str,
        pending_bindings: tuple[TermBinding, ...] = (),
    ) -> tuple[PrefixEquation, ...] | None:
        if logic.lower() not in _INTUITIONISTIC_LOGICS:
            return self._prefix_equations_for(
                older.prefix,
                older_instance,
                newer.prefix,
                newer_instance,
                logic=logic,
                domain=domain,
                pending_bindings=pending_bindings,
            )
        if older.polarity is False and newer.polarity is True:
            negative = older
            negative_instance = older_instance
            positive = newer
            positive_instance = newer_instance
        elif newer.polarity is False and older.polarity is True:
            negative = newer
            negative_instance = newer_instance
            positive = older
            positive_instance = older_instance
        else:
            negative = older
            negative_instance = older_instance
            positive = newer
            positive_instance = newer_instance
        return self._prefix_equations_for(
            negative.prefix,
            negative_instance,
            positive.prefix,
            positive_instance,
            logic=logic,
            domain=domain,
            pending_bindings=pending_bindings,
        )

    def _prefixes_satisfied(
        self,
        older: Prefix | None,
        older_instance: int | None,
        newer: Prefix | None,
        newer_instance: int | None,
        *,
        logic: str,
        domain: str,
    ) -> bool:
        if logic.lower() in _CLASSICAL_LOGICS:
            return True
        left_prefix = self._substituted_prefix(
            _literal_prefix(older),
            older_instance,
            pending_bindings=(),
        )
        right_prefix = self._substituted_prefix(
            _literal_prefix(newer),
            newer_instance,
            pending_bindings=(),
        )
        return self.prefixes.satisfied(
            left_prefix,
            None,
            right_prefix,
            None,
            logic=logic,
            domain=domain,
        )

    def _substituted_prefix(
        self,
        prefix: Prefix,
        instance_id: int | None,
        *,
        pending_bindings: tuple[TermBinding, ...],
    ) -> Prefix:
        return Prefix(
            tuple(
                self._substituted_prefix_part(
                    part,
                    instance_id,
                    pending_bindings=pending_bindings,
                )
                for part in prefix.parts
            )
        )

    def _substituted_prefix_part(
        self,
        part: Any,
        instance_id: int | None,
        *,
        pending_bindings: tuple[TermBinding, ...],
    ) -> Any:
        if type(part) is tuple:
            return tuple(
                self._substituted_prefix_part(
                    item,
                    instance_id,
                    pending_bindings=pending_bindings,
                )
                for item in part
            )
        if not isinstance(part, (Variable, Function, TableauVariable)):
            return part
        resolved = self.terms.substitute_term(
            part,
            instance_id=instance_id,
            pending_bindings=pending_bindings,
        )
        return _prefix_substitution_term(resolved)

    def _free_variable_admissibility_inputs(
        self,
        refs: tuple[FreeVariableReference, ...],
        *,
        pending_bindings: tuple[TermBinding, ...],
    ) -> tuple[tuple[Variable, ...], dict[Variable, Term]]:
        variables: list[Variable] = []
        resolved_terms: dict[Variable, Term] = {}
        for source, instance_id in refs:
            resolved = self._resolved_free_variable_term(
                source,
                instance_id,
                pending_bindings=pending_bindings,
            )
            if isinstance(resolved, (Variable, TableauVariable)):
                variables.append(
                    _free_variable_with_prefix(
                        _admissibility_term(resolved),
                        source.prefix,
                    )
                )
                continue
            variable = _scoped_free_variable(source, instance_id, prefix=source.prefix)
            variables.append(variable)
            resolved_terms[variable] = _admissibility_term(resolved)
        return tuple(variables), resolved_terms

    def _resolved_free_variable_term(
        self,
        variable: Variable,
        instance_id: int | None,
        *,
        pending_bindings: tuple[TermBinding, ...],
    ) -> TermSubstitutionTerm:
        unprefixed = _unprefixed_variable(variable)
        resolved = self.terms.substitute_term(
            unprefixed,
            instance_id=instance_id,
            pending_bindings=pending_bindings,
        )
        if variable.prefix is None or not _same_unresolved(
            resolved,
            unprefixed,
            instance_id,
        ):
            return resolved
        prefixed_resolved = self.terms.substitute_term(
            variable,
            instance_id=instance_id,
            pending_bindings=pending_bindings,
        )
        if _same_unresolved(prefixed_resolved, variable, instance_id):
            return resolved
        return prefixed_resolved


def _literal_prefix(prefix: Prefix | None) -> Prefix:
    return Prefix(()) if prefix is None else prefix


def _unprefixed_variable(variable: Variable) -> Variable:
    return Variable(variable.symbol, vid=variable.vid)


def _same_unresolved(
    term: TermSubstitutionTerm,
    variable: Variable,
    instance_id: int | None,
) -> bool:
    if isinstance(term, TableauVariable):
        return (
            instance_id is not None
            and term.instance_id == instance_id
            and (
                term.source.symbol,
                term.source.vid,
            )
            == (variable.symbol, variable.vid)
        )
    return (
        instance_id is None
        and type(term) is Variable
        and (
            term.symbol,
            term.vid,
        )
        == (variable.symbol, variable.vid)
    )


def _admissibility_term(term: TermSubstitutionTerm) -> Term:
    if isinstance(term, TableauVariable):
        return _scoped_free_variable(term.source, term.instance_id)
    if type(term) is Variable:
        return _unprefixed_variable(term)
    if type(term) is Function:
        return Function(
            term.symbol,
            tuple(_admissibility_term(arg) for arg in term.args),
            term.prefix,
        )
    raise TypeError(f"unsupported term: {term!r}")


def _prefix_substitution_term(term: TermSubstitutionTerm) -> Term:
    if isinstance(term, TableauVariable):
        return _prefix_scoped_variable(term.source, term.instance_id)
    if type(term) is Variable:
        return term
    if type(term) is Function:
        prefix = (
            None
            if term.prefix is None
            else Prefix(tuple(_prefix_substitution_term(part) for part in term.prefix.parts))
        )
        return Function(
            term.symbol,
            tuple(_prefix_substitution_term(arg) for arg in term.args),
            prefix,
        )
    raise TypeError(f"unsupported term: {term!r}")


def _prefix_scoped_variable(variable: Variable, instance_id: int) -> Variable:
    marker = Prefix(
        (
            Function("$prefix_instance", (Function(str(instance_id)),)),
            *(variable.prefix.parts if variable.prefix is not None else ()),
        )
    )
    return Variable(variable.symbol, prefix=marker, vid=variable.vid)


def _free_variable_with_prefix(variable: Term, prefix: Prefix | None) -> Variable:
    if type(variable) is not Variable:
        raise TypeError(f"expected variable, got {variable!r}")
    return Variable(variable.symbol, prefix=prefix, vid=variable.vid)


def _scoped_free_variable(
    variable: Variable,
    instance_id: int | None,
    *,
    prefix: Prefix | None = None,
) -> Variable:
    symbol = (
        variable.symbol if instance_id is None else f"{variable.symbol}@{instance_id}"
    )
    return Variable(symbol, prefix=prefix, vid=variable.vid)


__all__ = [
    "ConstraintStore",
]
