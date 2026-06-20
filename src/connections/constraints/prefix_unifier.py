from __future__ import annotations

from typing import Any

from connections.syntax.formula import Function, Variable
from connections.constraints.prefix_types import PrefixBinding


class PrefixUnifier:
    def __init__(
        self,
        left: tuple[Any, ...],
        right: tuple[Any, ...],
        *,
        initial_env: dict[Variable, Any] | None = None,
    ) -> None:
        self._fresh_id = 0
        self._source_variables = prefix_variables(left) | prefix_variables(right)
        self._initial_env = dict(initial_env or {})

    def bindings_from_env(
        self,
        env: dict[Variable, Any] | None,
    ) -> tuple[PrefixBinding, ...] | None:
        if env is None:
            return None
        bindings = [
            PrefixBinding(variable, self._target_tuple(env[variable], env))
            for variable in sorted(
                _public_variables(self._source_variables & env.keys()),
                key=lambda value: (value.symbol, value.vid),
            )
        ]
        return tuple(
            binding
            for binding in bindings
            if binding.target != (binding.variable,)
        )

    def _env(self) -> dict[Variable, Any]:
        return dict(self._initial_env)

    def _target_tuple(self, value: Any, env: dict[Variable, Any]) -> tuple[Any, ...]:
        value = self._resolve(value, env)
        if type(value) is tuple:
            return tuple(self._target_part(part, env) for part in value)
        return (self._target_part(value, env),)

    def _target_part(self, value: Any, env: dict[Variable, Any]) -> Any:
        value = self._resolve(value, env)
        if type(value) is tuple:
            return tuple(self._target_part(part, env) for part in value)
        return value

    def t_unify(
        self,
        left: tuple[Any, ...],
        right: tuple[Any, ...],
    ) -> dict[Variable, Any] | None:
        return self._tuni_t(left, (), right, self._env())

    def d_unify(
        self,
        left: tuple[Any, ...],
        right: tuple[Any, ...],
    ) -> dict[Variable, Any] | None:
        if len(left) != len(right):
            return None
        env = self._env()
        if all(self._unify_mut(a, b, env) for a, b in zip(left, right)):
            return env
        return None

    def s4_unify(
        self,
        left: tuple[Any, ...],
        right: tuple[Any, ...],
    ) -> dict[Variable, Any] | None:
        return self._tunify(left, (), right, self._env())

    def s5_unify(
        self,
        left: tuple[Any, ...],
        right: tuple[Any, ...],
    ) -> dict[Variable, Any] | None:
        if not left and not right:
            return self._env()
        if not right:
            return self._unify(left[-1], (), self._env())
        if not left:
            return self._unify(right[-1], (), self._env())
        return self._unify(left[-1], right[-1], self._env())

    def _tuni_t(
        self,
        left: tuple[Any, ...],
        z: tuple[Any, ...],
        right: tuple[Any, ...],
        env: dict[Variable, Any],
    ) -> dict[Variable, Any] | None:
        if not left and not z and not right:
            return env
        if not left and not z and right:
            return self._tuni_t(right, (), (), env.copy())
        if left and not z and not right:
            next_env = self._unify(left[0], (), env)
            if next_env is not None:
                return self._tuni_t(left[1:], (), (), next_env)
            return None
        if left and not z and right:
            next_env = self._tuni_t_equal_heads(left[0], right[0], env)
            if next_env is not None:
                result = self._tuni_t(left[1:], (), right[1:], next_env)
                if result is not None:
                    return result
            if self._is_var(left[0], env):
                result = self._tuni_t(left, (right[0],), right[1:], env.copy())
                if result is not None:
                    return result
            if self._is_nonvar(left[0], env) and self._is_var(right[0], env):
                result = self._tuni_t(right, (left[0],), left[1:], env.copy())
                if result is not None:
                    return result
            if self._is_var(left[0], env) and self._is_var(right[0], env):
                next_env = self._unify(right[0], (), env)
                if next_env is not None:
                    result = self._tuni_t(
                        right[1:],
                        (left[0],),
                        left[1:],
                        next_env,
                    )
                    if result is not None:
                        return result
        if left and len(z) == 1:
            next_env = self._unify(left[0], (), env)
            if next_env is not None:
                result = self._tuni_t(left[1:], z, right, next_env)
                if result is not None:
                    return result
            if self._is_var(left[0], env):
                next_env = self._unify(left[0], z[0], env)
                if next_env is not None:
                    result = self._tuni_t(left[1:], (), right, next_env)
                    if result is not None:
                        return result
            if self._is_nonvar(left[0], env) and self._is_var(z[0], env):
                next_env = self._unify(z[0], left[0], env)
                if next_env is not None:
                    result = self._tuni_t(left[1:], (), right, next_env)
                    if result is not None:
                        return result
        return None

    def _tuni_t_equal_heads(
        self,
        left: Any,
        right: Any,
        env: dict[Variable, Any],
    ) -> dict[Variable, Any] | None:
        if self._is_var(left, env):
            if self._is_var(right, env) and self._same_var(left, right, env):
                return env.copy()
            return None
        if self._is_nonvar(right, env):
            return self._unify(left, right, env)
        return None

    def _tunify(
        self,
        left: tuple[Any, ...],
        z: tuple[Any, ...],
        right: tuple[Any, ...],
        env: dict[Variable, Any],
    ) -> dict[Variable, Any] | None:
        if not left and not z and not right:
            return env
        if not left and not z and right:
            return self._tunify(right, (), (), env.copy())
        if left and not z and right:
            next_env = self._tunify_equal_heads(left[0], right[0], env)
            if next_env is not None:
                result = self._tunify(left[1:], (), right[1:], next_env)
                if result is not None:
                    return result
            if self._is_nonvar(left[0], env):
                if self._is_var(right[0], env):
                    return self._tunify(right, (), left, env.copy())
                return None
        if left and not right:
            next_env = self._unify(left[0], z, env)
            if next_env is not None:
                return self._tunify(left[1:], (), (), next_env)
            return None
        if left and not z and right and self._is_nonvar(right[0], env):
            next_env = self._unify(left[0], (), env)
            if next_env is not None:
                result = self._tunify(left[1:], (), right, next_env)
                if result is not None:
                    return result
        if (
            left
            and len(right) >= 2
            and self._is_nonvar(right[0], env)
            and self._is_nonvar(right[1], env)
        ):
            next_env = self._unify(left[0], z + (right[0],), env)
            if next_env is not None:
                result = self._tunify(left[1:], (), right[1:], next_env)
                if result is not None:
                    return result
        if len(left) >= 2 and not z and right and self._is_var(right[0], env):
            result = self._tunify(right, (left[0],), left[1:], env.copy())
            if result is not None:
                return result
        if len(left) >= 2 and z and right and self._is_var(right[0], env):
            fresh = self._fresh_variable()
            next_env = self._unify(left[0], z + (fresh,), env)
            if next_env is not None:
                result = self._tunify(right, (fresh,), left[1:], next_env)
                if result is not None:
                    return result
        if left and right and (
            len(left) == 1 or len(right) > 1 or self._is_nonvar(right[0], env)
        ):
            return self._tunify(left, z + (right[0],), right[1:], env.copy())
        return None

    def _tunify_equal_heads(
        self,
        left: Any,
        right: Any,
        env: dict[Variable, Any],
    ) -> dict[Variable, Any] | None:
        if self._is_var(left, env):
            if self._is_var(right, env) and self._same_var(left, right, env):
                return env.copy()
            return None
        if self._is_nonvar(right, env):
            return self._unify(left, right, env)
        return None

    def _unify(
        self,
        left: Any,
        right: Any,
        env: dict[Variable, Any],
    ) -> dict[Variable, Any] | None:
        next_env = env.copy()
        if self._unify_mut(left, right, next_env):
            return next_env
        return None

    def _unify_mut(
        self,
        left: Any,
        right: Any,
        env: dict[Variable, Any],
    ) -> bool:
        left = self._resolve(left, env)
        right = self._resolve(right, env)
        if left == right:
            return True
        if type(left) is Variable:
            return self._bind(left, right, env)
        if type(right) is Variable:
            return self._bind(right, left, env)
        if type(left) is tuple and type(right) is tuple:
            if len(left) != len(right):
                return False
            return all(self._unify_mut(a, b, env) for a, b in zip(left, right))
        if type(left) is Function and type(right) is Function:
            if left.symbol != right.symbol or len(left.args) != len(right.args):
                return False
            return all(
                self._unify_mut(a, b, env)
                for a, b in zip(left.args, right.args)
            )
        return False

    def _bind(
        self,
        variable: Variable,
        target: Any,
        env: dict[Variable, Any],
    ) -> bool:
        if self._occurs(variable, target, env):
            return False
        env[variable] = target
        return True

    def _occurs(
        self,
        variable: Variable,
        value: Any,
        env: dict[Variable, Any],
    ) -> bool:
        value = self._resolve(value, env)
        if value == variable:
            return True
        if type(value) is tuple:
            return any(self._occurs(variable, part, env) for part in value)
        if type(value) is Function:
            return any(self._occurs(variable, arg, env) for arg in value.args)
        return False

    def _resolve(self, value: Any, env: dict[Variable, Any]) -> Any:
        seen: set[Variable] = set()
        while type(value) is Variable and value in env and value not in seen:
            seen.add(value)
            value = env[value]
        return value

    def _is_var(self, value: Any, env: dict[Variable, Any]) -> bool:
        return type(self._resolve(value, env)) is Variable

    def _is_nonvar(self, value: Any, env: dict[Variable, Any]) -> bool:
        return not self._is_var(value, env)

    def _same_var(
        self,
        left: Any,
        right: Any,
        env: dict[Variable, Any],
    ) -> bool:
        left = self._resolve(left, env)
        right = self._resolve(right, env)
        return type(left) is Variable and type(right) is Variable and left == right

    def _fresh_variable(self) -> Variable:
        self._fresh_id += 1
        return Variable("$Prefix", vid=self._fresh_id)


def prefix_variables(prefix: tuple[Any, ...]) -> set[Variable]:
    variables: set[Variable] = set()
    for value in prefix:
        if type(value) is Variable:
            variables.add(value)
        elif type(value) is Function:
            variables.update(prefix_variables(value.args))
        elif type(value) is tuple:
            variables.update(prefix_variables(value))
    return variables


def _public_variables(variables: set[Variable]) -> set[Variable]:
    return {
        variable for variable in variables if not variable.symbol.startswith("$")
    }


__all__ = ["PrefixUnifier", "prefix_variables"]
