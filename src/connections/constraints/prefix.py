from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from connections.syntax.formula import Function, Prefix, Term, Variable
from connections.syntax.logic import (
    INTUITIONISTIC_LOGICS,
    SUPPORTED_DOMAINS,
    normalize_domain,
    normalize_logic,
)
from connections.constraints.prefix_types import PrefixBinding, PrefixEquation
from connections.constraints.prefix_unifier import PrefixUnifier, prefix_variables

_D_LOGICS = {"d"}
_T_LOGICS = {"t"}
_S4_LOGICS = {"s4"}
_S5_LOGICS = {"s5"}
_INTERNAL_VARIABLE_PREFIX = "$IntuitionisticPrefix"


class PrefixConstraintStore:
    def __init__(self) -> None:
        self._equations: list[PrefixEquation] = []
        self._equation_owner_app_ids: list[int | None] = []
        self.revision = 0

    @property
    def equations(self) -> tuple[PrefixEquation, ...]:
        return tuple(self._equations)

    def delta_for(
        self,
        left: Prefix,
        left_instance: int | None,
        right: Prefix,
        right_instance: int | None,
        *,
        logic: str,
        domain: str,
    ) -> tuple[PrefixEquation, ...] | None:
        equation = PrefixEquation(
            _scope_prefix(left, left_instance),
            _scope_prefix(right, right_instance),
        )
        if equation.left == equation.right or self._has_equation(equation):
            return ()
        if prefix_equations_satisfiable(
            (equation,),
            logic=logic,
            domain=domain,
        ):
            return (equation,)
        return None

    def satisfiable(self, *, logic: str, domain: str) -> bool:
        return prefix_equations_satisfiable(
            self.equations,
            logic=logic,
            domain=domain,
        )

    def satisfied(
        self,
        left: Prefix,
        left_instance: int | None,
        right: Prefix,
        right_instance: int | None,
        *,
        logic: str,
        domain: str,
    ) -> bool:
        _validate_domain(domain)
        _validate_logic(logic)
        equation = PrefixEquation(
            _scope_prefix(left, left_instance),
            _scope_prefix(right, right_instance),
        )
        return equation.left == equation.right

    def commit(
        self,
        equations: tuple[PrefixEquation, ...],
        *,
        owner_app_id: int | None = None,
    ) -> None:
        if not equations:
            return
        for equation in equations:
            self._equations.append(equation)
            self._equation_owner_app_ids.append(owner_app_id)
        self.revision += 1

    def rollback_owned_by(self, owner_app_ids: tuple[int, ...] | set[int]) -> None:
        if not owner_app_ids:
            return
        owner_id_set = set(owner_app_ids)
        kept = [
            (equation, owner_app_id)
            for equation, owner_app_id in zip(
                self._equations,
                self._equation_owner_app_ids,
                strict=True,
            )
            if owner_app_id not in owner_id_set
        ]
        if len(kept) == len(self._equations):
            return
        self._equations = [equation for equation, _ in kept]
        self._equation_owner_app_ids = [owner_app_id for _, owner_app_id in kept]
        self.revision += 1

    def _has_equation(self, equation: PrefixEquation) -> bool:
        return any(
            equation == current
            or (
                equation.left == current.right
                and equation.right == current.left
            )
            for current in self._equations
        )


def prefix_unify_from_empty(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    domain: str,
) -> tuple[PrefixBinding, ...] | None:
    return _prefix_unify(left, right, logic=logic, domain=domain)


def _prefix_unify(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    domain: str,
) -> tuple[PrefixBinding, ...] | None:
    env = _prefix_unify_env(
        left,
        right,
        logic=logic,
        domain=domain,
    )
    return PrefixUnifier(left.parts, right.parts).bindings_from_env(env)


def prefix_equations_satisfiable(
    equations: tuple[PrefixEquation, ...],
    *,
    logic: str,
    domain: str,
) -> bool:
    env: dict[Variable, Any] = {}
    for equation in equations:
        next_env = _prefix_unify_env(
            equation.left,
            equation.right,
            logic=logic,
            domain=domain,
            initial_env=env,
        )
        if next_env is None:
            return False
        env = next_env
    return True


def free_variables_admissible(
    free_variables: tuple[Variable, ...],
    *,
    logic: str,
    domain: str,
    resolved_terms: Mapping[Variable, Term] | None = None,
) -> bool:
    _validate_logic(logic)
    normalized_domain = _normalize_domain_checked(domain)
    first_variable_prefixes: dict[Variable, Prefix] = {}
    for variable in free_variables:
        if variable.prefix is None:
            raise ValueError(f"free variable has no prefix: {variable!r}")
        first_variable_prefixes.setdefault(
            _unprefixed_variable(variable),
            variable.prefix,
        )

    if normalized_domain == "const":
        return True

    resolved_terms = {} if resolved_terms is None else resolved_terms
    env: dict[Variable, Any] = {}
    for variable in free_variables:
        prefix = variable.prefix
        if prefix is None:
            raise AssertionError("free variable prefix was validated above")
        resolved_term = resolved_terms.get(variable, _unprefixed_variable(variable))
        next_env = _free_variable_term_env(
            resolved_term,
            prefix,
            first_variable_prefixes,
            logic=logic,
            domain=normalized_domain,
            initial_env=env,
        )
        if next_env is None:
            return False
        env = next_env
    return True


def prefixes_admissible(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    domain: str,
) -> bool:
    return (
        _prefix_admissibility_env(
            left,
            right,
            logic=logic,
            domain=domain,
        )
        is not None
    )


def _prefix_unify_env(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    domain: str,
    initial_env: dict[Variable, Any] | None = None,
) -> dict[Variable, Any] | None:
    _validate_domain(domain)
    normalized_logic = normalize_logic(logic)
    initial_env = dict(initial_env or {})
    flatten_prefixes = normalized_logic not in _S5_LOGICS
    left_parts = _instantiate_prefix_parts(
        left.parts,
        initial_env,
        flatten_prefixes=flatten_prefixes,
    )
    right_parts = _instantiate_prefix_parts(
        right.parts,
        initial_env,
        flatten_prefixes=flatten_prefixes,
    )
    if normalized_logic in INTUITIONISTIC_LOGICS:
        left_parts = (
            *left_parts,
            _fresh_internal_prefix_variable(left_parts, right_parts, initial_env),
        )
    unifier = PrefixUnifier(
        left_parts,
        right_parts,
        initial_env=initial_env,
    )
    if normalized_logic in _D_LOGICS:
        return unifier.d_unify(left_parts, right_parts)
    if normalized_logic in _T_LOGICS:
        return unifier.t_unify(left_parts, right_parts)
    if normalized_logic in _S4_LOGICS:
        return unifier.s4_unify(left_parts, right_parts)
    if normalized_logic in _S5_LOGICS:
        return unifier.s5_unify(left_parts, right_parts)
    if normalized_logic in INTUITIONISTIC_LOGICS:
        return unifier.s4_unify(left_parts, right_parts)
    _validate_logic(logic)
    raise AssertionError("unreachable")


def _free_variable_term_env(
    term: Term,
    prefix: Prefix,
    first_variable_prefixes: dict[Variable, Prefix],
    *,
    logic: str,
    domain: str,
    initial_env: dict[Variable, Any],
) -> dict[Variable, Any] | None:
    env = initial_env
    term_prefix = term.prefix
    if term_prefix is not None:
        return _prefix_admissibility_env(
            term_prefix,
            prefix,
            logic=logic,
            domain=domain,
            initial_env=env,
        )
    if type(term) is Variable:
        if domain != "vary":
            return env
        variable_prefix = first_variable_prefixes.get(_unprefixed_variable(term))
        if variable_prefix is None:
            return None
        return _prefix_admissibility_env(
            variable_prefix,
            prefix,
            logic=logic,
            domain=domain,
            initial_env=env,
        )
    if type(term) is not Function:
        raise TypeError(f"unsupported term: {term!r}")
    for arg in term.args:
        env = _free_variable_term_env(
            arg,
            prefix,
            first_variable_prefixes,
            logic=logic,
            domain=domain,
            initial_env=env,
        )
        if env is None:
            return None
    return env


def _prefix_admissibility_env(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    domain: str,
    initial_env: dict[Variable, Any] | None = None,
) -> dict[Variable, Any] | None:
    normalized_domain = _normalize_domain_checked(domain)
    if normalized_domain == "const":
        return dict(initial_env or {})
    if normalized_domain == "vary":
        return _prefix_unify_env(
            left,
            right,
            logic=logic,
            domain=domain,
            initial_env=initial_env,
        )
    return _cumulative_prefix_admissibility_env(
        left,
        right,
        logic=logic,
        initial_env=initial_env,
    )


def _cumulative_prefix_admissibility_env(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    initial_env: dict[Variable, Any] | None = None,
) -> dict[Variable, Any] | None:
    normalized_logic = normalize_logic(logic)
    env = dict(initial_env or {})
    if normalized_logic in _S5_LOGICS:
        return env

    left_parts = _instantiate_prefix_parts(
        left.parts,
        env,
        flatten_prefixes=True,
    )
    right_parts = _instantiate_prefix_parts(
        right.parts,
        env,
        flatten_prefixes=True,
    )
    unifier = PrefixUnifier(
        left_parts,
        right_parts,
        initial_env=env,
    )
    if normalized_logic in _D_LOGICS:
        if len(right_parts) < len(left_parts):
            return None
        return unifier.d_unify(left_parts, right_parts[: len(left_parts)])
    if normalized_logic in _T_LOGICS:
        for size in range(len(right_parts) + 1):
            prefix = right_parts[:size]
            if prefix and _empty_prefix_part(prefix[-1]):
                continue
            result = unifier.t_unify(left_parts, prefix)
            if result is not None:
                return result
        return None
    if normalized_logic in _S4_LOGICS:
        left_extended = (
            *left_parts,
            _fresh_internal_prefix_variable(left_parts, right_parts, env),
        )
        return unifier.s4_unify(left_extended, right_parts)
    if normalized_logic in INTUITIONISTIC_LOGICS:
        return _prefix_unify_env(
            left,
            right,
            logic=logic,
            domain="cumul",
            initial_env=initial_env,
        )
    _validate_logic(logic)
    raise AssertionError("unreachable")


def prefix_unifiable_from_empty(
    left: Prefix,
    right: Prefix,
    *,
    logic: str,
    domain: str,
) -> bool:
    """Return whether two prefixes are unifiable without committed bindings.

    This is native parity code for the leanCoP-family modal prefix rules.
    """
    return prefix_unify_from_empty(left, right, logic=logic, domain=domain) is not None


def _validate_domain(domain: str) -> None:
    _normalize_domain_checked(domain)


def _normalize_domain_checked(domain: str) -> str:
    normalized = normalize_domain(domain)
    if normalized not in SUPPORTED_DOMAINS:
        raise ValueError(f"unsupported domain: {domain!r}")
    return normalized


def _validate_logic(logic: str) -> None:
    normalized_logic = normalize_logic(logic)
    if (
        normalized_logic not in _D_LOGICS
        and normalized_logic not in _T_LOGICS
        and normalized_logic not in _S4_LOGICS
        and normalized_logic not in _S5_LOGICS
        and normalized_logic not in INTUITIONISTIC_LOGICS
    ):
        raise NotImplementedError(
            f"native prefix unification is not implemented for {logic!r}"
        )


def _instantiate_prefix_parts(
    parts: tuple[Any, ...],
    env: dict[Variable, Any],
    *,
    flatten_prefixes: bool,
) -> tuple[Any, ...]:
    output: list[Any] = []
    for part in parts:
        resolved = _resolve_env_value(part, env)
        if flatten_prefixes and type(resolved) is tuple:
            output.extend(resolved)
        else:
            output.append(resolved)
    return tuple(output)


def _resolve_env_value(value: Any, env: dict[Variable, Any]) -> Any:
    seen: set[Variable] = set()
    while type(value) is Variable and value in env and value not in seen:
        seen.add(value)
        value = env[value]
    if type(value) is tuple:
        return tuple(_resolve_env_value(part, env) for part in value)
    if type(value) is Function:
        return value
    return value


def _scope_prefix(prefix: Prefix, instance_id: int | None) -> Prefix:
    if instance_id is None:
        return prefix
    return Prefix(tuple(_scope_prefix_part(part, instance_id) for part in prefix.parts))


def _scope_prefix_part(value: Any, instance_id: int) -> Any:
    if type(value) is Variable:
        return _scoped_variable(value, instance_id)
    if type(value) is Function:
        return Function(
            value.symbol,
            tuple(_scope_prefix_part(arg, instance_id) for arg in value.args),
            value.prefix,
        )
    if type(value) is tuple:
        return tuple(_scope_prefix_part(part, instance_id) for part in value)
    return value


def _scoped_variable(variable: Variable, instance_id: int) -> Variable:
    marker = Prefix(
        (
            Function("$prefix_instance", (Function(str(instance_id)),)),
            *(variable.prefix.parts if variable.prefix is not None else ()),
        )
    )
    return Variable(variable.symbol, prefix=marker, vid=variable.vid)


def _unprefixed_variable(variable: Variable) -> Variable:
    if variable.prefix is None:
        return variable
    return Variable(variable.symbol, vid=variable.vid)


def _fresh_internal_prefix_variable(
    left: tuple[Any, ...],
    right: tuple[Any, ...],
    env: dict[Variable, Any],
) -> Variable:
    variables = set(env) | prefix_variables(left) | prefix_variables(right)
    vid = 1
    while True:
        candidate = Variable(_INTERNAL_VARIABLE_PREFIX, vid=vid)
        if candidate not in variables:
            return candidate
        vid += 1


def _empty_prefix_part(part: Any) -> bool:
    return type(part) is tuple and len(part) == 0


__all__ = [
    "PrefixBinding",
    "PrefixConstraintStore",
    "PrefixEquation",
    "free_variables_admissible",
    "prefixes_admissible",
    "prefix_equations_satisfiable",
    "prefix_unify_from_empty",
    "prefix_unifiable_from_empty",
]
