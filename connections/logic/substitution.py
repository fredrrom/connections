from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from connections.logic.syntax import Function, Literal, Prefix, Term, Variable


@dataclass(frozen=True)
class SubstitutionUpdate:
    var: Variable
    old_assignment: Optional[Any]
    new_assignment: Optional[Any]


class Substitution:
    def __init__(self) -> None:
        self.bindings: Dict[Variable, Any] = {}

    def unify(self, s: Any, t: Any) -> Tuple[bool, List[SubstitutionUpdate]]:
        raise NotImplementedError

    def update(self, updates: List[SubstitutionUpdate]) -> None:
        for update in updates:
            if update.new_assignment is None:
                self.bindings.pop(update.var, None)
            else:
                self.bindings[update.var] = update.new_assignment

    def revert(self, updates: List[SubstitutionUpdate]) -> None:
        for update in reversed(updates):
            if update.old_assignment is None:
                self.bindings.pop(update.var, None)
            else:
                self.bindings[update.var] = update.old_assignment

    def equal(self, s: Any, t: Any) -> bool:
        raise NotImplementedError

    def __repr__(self) -> str:
        rendered = ", ".join(
            f"{var} -> {self._find(value)}" for var, value in self.bindings.items()
        )
        return "{" + rendered + "}"

    def _find(self, value: Any) -> Any:
        while isinstance(value, Variable) and value in self.bindings:
            value = self.bindings[value]
        return value


class TermSubstitution(Substitution):
    def __init__(self) -> None:
        super().__init__()
        self.bindings: Dict[Variable, Term] = {}

    def occurs(
        self, var: Variable, value: Any, work: Optional[Dict[Variable, Any]] = None
    ) -> bool:
        resolved = self._resolve(value, work)
        if resolved == var:
            return True
        if isinstance(resolved, Prefix):
            return any(self.occurs(var, part, work) for part in resolved.parts)
        if isinstance(resolved, (Term, Literal)):
            if any(self.occurs(var, arg, work) for arg in resolved.args):
                return True
            if resolved.prefix is not None:
                return self.occurs(var, resolved.prefix, work)
        return False

    def _resolve(self, value: Any, work: Optional[Dict[Variable, Any]] = None) -> Any:
        lookup = work if work is not None else self.bindings
        while isinstance(value, Variable) and value in lookup:
            value = lookup[value]
        return value

    def unify(self, s: Any, t: Any) -> Tuple[bool, List[SubstitutionUpdate]]:
        work: Dict[Variable, Any] = dict(self.bindings)
        updates: List[SubstitutionUpdate] = []
        equations = [(s, t)]

        while equations:
            left, right = equations.pop()
            left = self._resolve(left, work)
            right = self._resolve(right, work)

            if left == right:
                continue

            if isinstance(left, Variable) and isinstance(right, Variable):
                if self.occurs(left, right, work) or self.occurs(right, left, work):
                    return False, []
                var, value = (right, left) if left.vid < right.vid else (left, right)
                if var in work:
                    return False, []
                updates.append(SubstitutionUpdate(var, work.get(var), value))
                work[var] = value
                continue

            if isinstance(left, Variable):
                if self.occurs(left, right, work):
                    return False, []
                if left in work:
                    return False, []
                updates.append(SubstitutionUpdate(left, work.get(left), right))
                work[left] = right
                continue

            if isinstance(right, Variable):
                if self.occurs(right, left, work):
                    return False, []
                if right in work:
                    return False, []
                updates.append(SubstitutionUpdate(right, work.get(right), left))
                work[right] = left
                continue

            if isinstance(left, Prefix) and isinstance(right, Prefix):
                if len(left.parts) != len(right.parts):
                    return False, []
                for l_part, r_part in zip(left.parts, right.parts):
                    equations.append((l_part, r_part))
                continue

            if not isinstance(left, (Term, Literal)) or not isinstance(
                right, (Term, Literal)
            ):
                return False, []
            if left.name != right.name or len(left.args) != len(right.args):
                return False, []
            for l_arg, r_arg in zip(left.args, right.args):
                equations.append((l_arg, r_arg))
            if left.prefix is None and right.prefix is None:
                continue
            if left.prefix is None or right.prefix is None:
                return False, []
            equations.append((left.prefix, right.prefix))

        return True, updates

    def equal(self, s: Any, t: Any) -> bool:
        s = self._resolve(s)
        t = self._resolve(t)
        if s == t:
            return True
        if isinstance(s, Prefix) and isinstance(t, Prefix):
            return len(s.parts) == len(t.parts) and all(
                self.equal(a, b) for a, b in zip(s.parts, t.parts)
            )
        if isinstance(s, (Term, Literal)) and isinstance(t, (Term, Literal)):
            if s.name != t.name or len(s.args) != len(t.args):
                return False
            if not all(self.equal(a, b) for a, b in zip(s.args, t.args)):
                return False
            if s.prefix is None and t.prefix is None:
                return True
            if s.prefix is None or t.prefix is None:
                return False
            return self.equal(s.prefix, t.prefix)
        return False

    def __call__(self, value: Any) -> Any:
        value = self._resolve(value)
        if isinstance(value, Prefix):
            return Prefix(tuple(self(part) for part in value.parts))
        if isinstance(value, Variable):
            return value
        if isinstance(value, Term):
            args = tuple(self(arg) for arg in value.args)
            prefix = self(value.prefix) if value.prefix is not None else None
            return type(value)(value.name, args=args, prefix=prefix)
        if isinstance(value, Literal):
            args = tuple(self(arg) for arg in value.args)
            prefix = self(value.prefix) if value.prefix is not None else None
            return Literal(value.name, args=args, prefix=prefix, neg=value.neg)
        return value


class PrefixSubstitution(Substitution):
    def __init__(
        self,
        logic: str = "intuitionistic",
        domain: str = "constant",
        term_substitution: Optional[TermSubstitution] = None,
    ) -> None:
        super().__init__()
        self.logic = logic
        self.domain = domain
        self.term_substitution = term_substitution
        self.bindings: Dict[Variable, Prefix] = {}

    def bind_term_substitution(self, term_substitution: TermSubstitution) -> None:
        self.term_substitution = term_substitution

    def normalize(self, prefix: Prefix) -> Prefix:
        if self.logic == "S5" and prefix.parts:
            return Prefix((prefix.parts[-1],))
        return prefix

    def is_active(self) -> bool:
        return self.logic != "classical"

    def should_collect_admissible_pairs(self) -> bool:
        if self.logic == "classical":
            return False
        if self.logic in {"D", "T", "S4"} and self.domain == "constant":
            return False
        if self.logic == "S5" and self.domain in {"constant", "cumulative"}:
            return False
        return True

    def _as_prefix(self, value: Any) -> Prefix:
        if isinstance(value, Prefix):
            return self.normalize(value)
        if isinstance(value, tuple):
            return self.normalize(Prefix(value))
        if isinstance(value, list):
            return self.normalize(Prefix(tuple(value)))
        if hasattr(value, "name") and getattr(value, "name") == "string":
            return self.normalize(Prefix(tuple(value.args)))
        if isinstance(value, Term):
            return self.normalize(Prefix((value,)))
        raise TypeError(f"Unsupported prefix value: {type(value)!r}")

    def _resolve(
        self, value: Any, work: Optional[Dict[Variable, Prefix]] = None
    ) -> Any:
        lookup = work if work is not None else self.bindings
        while isinstance(value, Variable) and value in lookup:
            bound = lookup[value]
            if len(bound.parts) == 1:
                value = bound.parts[0]
            else:
                value = bound
        return value

    def occurs(
        self, var: Variable, value: Any, work: Optional[Dict[Variable, Prefix]] = None
    ) -> bool:
        resolved = self._resolve(value, work)
        if resolved == var:
            return True
        if isinstance(resolved, Prefix):
            return any(self.occurs(var, part, work) for part in resolved.parts)
        if isinstance(resolved, Function):
            return any(self.occurs(var, arg, work) for arg in resolved.args)
        return False

    def unify(self, s: Any, t: Any) -> Tuple[bool, List[SubstitutionUpdate]]:
        work: Dict[Variable, Prefix] = dict(self.bindings)
        updates: List[SubstitutionUpdate] = []
        equations = [(self._as_prefix(s), self._as_prefix(t))]
        term_sub = self.term_substitution or TermSubstitution()

        while equations:
            left, right = equations.pop()
            left = self._resolve(left, work)
            right = self._resolve(right, work)

            if left == right:
                continue

            if isinstance(left, Prefix) and isinstance(right, Prefix):
                if len(left.parts) != len(right.parts):
                    return False, []
                for l_part, r_part in zip(left.parts, right.parts):
                    equations.append((l_part, r_part))
                continue

            if isinstance(left, Variable):
                right_prefix = self._as_prefix(right)
                if self.occurs(left, right_prefix, work):
                    return False, []
                updates.append(SubstitutionUpdate(left, work.get(left), right_prefix))
                work[left] = right_prefix
                continue

            if isinstance(right, Variable):
                left_prefix = self._as_prefix(left)
                if self.occurs(right, left_prefix, work):
                    return False, []
                updates.append(SubstitutionUpdate(right, work.get(right), left_prefix))
                work[right] = left_prefix
                continue

            ok, _ = term_sub.unify(left, right)
            if not ok:
                return False, []

        return True, updates

    def equal(self, s: Any, t: Any) -> bool:
        left = self._resolve(s)
        right = self._resolve(t)
        if left == right:
            return True
        if isinstance(left, Prefix) and isinstance(right, Prefix):
            return len(left.parts) == len(right.parts) and all(
                self.equal(a, b) for a, b in zip(left.parts, right.parts)
            )
        if isinstance(left, Function) and isinstance(right, Function):
            return (
                left.name == right.name
                and len(left.args) == len(right.args)
                and all(self.equal(a, b) for a, b in zip(left.args, right.args))
            )
        return False

    def __call__(self, value: Any) -> Any:
        value = self._resolve(value)
        if isinstance(value, Prefix):
            return Prefix(tuple(self(part) for part in value.parts))
        if isinstance(value, Function):
            args = tuple(self(arg) for arg in value.args)
            return Function(value.name, args=args, prefix=value.prefix)
        return value

    def relation_pair(
        self,
        lit_1: Any,
        lit_2: Any,
        fresh_variable: Optional[Variable] = None,
    ) -> Tuple[Prefix, Prefix]:
        left = lit_1
        right = lit_2

        if self.logic == "intuitionistic":
            if not left.neg:
                left, right = right, left
            left_prefix = self._as_prefix(
                left.prefix if left.prefix is not None else Prefix(())
            )
            right_prefix = self._as_prefix(
                right.prefix if right.prefix is not None else Prefix(())
            )
            if fresh_variable is None:
                return left_prefix, right_prefix
            return Prefix(left_prefix.parts + (fresh_variable,)), right_prefix

        left_prefix = self._as_prefix(
            left.prefix if left.prefix is not None else Prefix(())
        )
        right_prefix = self._as_prefix(
            right.prefix if right.prefix is not None else Prefix(())
        )
        if self.logic == "S5":
            left_prefix = (
                Prefix(left_prefix.parts[-1:]) if left_prefix.parts else Prefix(())
            )
            right_prefix = (
                Prefix(right_prefix.parts[-1:]) if right_prefix.parts else Prefix(())
            )
        return left_prefix, right_prefix

    def relation_ok(
        self,
        left_literal: Any,
        right_literal: Any,
        term_substitution: TermSubstitution,
        term_updates: List[SubstitutionUpdate],
        fresh_variable: Any,
    ) -> bool:
        if not self.is_active():
            return True
        self.bind_term_substitution(term_substitution)
        left_prefix, right_prefix = self.relation_pair(
            left_literal,
            right_literal,
            fresh_variable=fresh_variable(),
        )
        term_substitution.update(term_updates)
        ok, _ = self.unify(left_prefix, right_prefix)
        term_substitution.revert(term_updates)
        return ok

    def admissible_pair(
        self,
        var_prefix: Prefix,
        eigen_prefix: Prefix,
        fresh_variable: Optional[Variable] = None,
    ) -> Optional[Tuple[Prefix, Prefix]]:
        left = self._as_prefix(var_prefix)
        right = self._as_prefix(eigen_prefix)

        if not self.should_collect_admissible_pairs():
            return None

        if self.logic in {"intuitionistic", "S4"}:
            if self.logic == "S4" and self.domain == "varying":
                return left, right
            if fresh_variable is None:
                return left, right
            return left, Prefix(right.parts + (fresh_variable,))

        if self.logic in {"D", "T"}:
            if self.domain == "cumulative":
                return Prefix(left.parts[: len(right.parts)]), right
            return left, right

        if self.logic == "S5" and self.domain == "varying":
            left_last = Prefix(left.parts[-1:]) if left.parts else Prefix(())
            right_last = Prefix(right.parts[-1:]) if right.parts else Prefix(())
            return left_last, right_last

        return None

    def eigenvariables(self, term: Any) -> List[Any]:
        if isinstance(term, Function) and term.name == "f_skolem":
            return [term]
        if isinstance(term, Function):
            found: List[Any] = []
            for subterm in term.args:
                found.extend(self.eigenvariables(subterm))
            return found
        return []

    def proof_unifier(
        self,
        term_substitution: TermSubstitution,
        proof_sequence: List[Any],
        fresh_variable: Any,
    ) -> Tuple[bool, List[SubstitutionUpdate]]:
        if not self.is_active():
            return True, []

        self.bind_term_substitution(term_substitution)
        equations: List[Tuple[Prefix, Prefix]] = []

        if self.should_collect_admissible_pairs():
            for var, term in term_substitution.bindings.items():
                var_prefix = var.prefix if var.prefix is not None else Prefix(())
                resolved_term = term_substitution(term)
                for eigen in self.eigenvariables(resolved_term):
                    eigen_prefix = (
                        eigen.prefix if eigen.prefix is not None else Prefix(())
                    )
                    pair = self.admissible_pair(
                        var_prefix,
                        eigen_prefix,
                        fresh_variable=fresh_variable(),
                    )
                    if pair is not None:
                        equations.append(pair)

        for action in proof_sequence:
            if (
                action.action_type == "reduction"
                and action.path_node is not None
                and action.principle_node.literal is not None
                and action.path_node.literal is not None
            ):
                equations.append(
                    self.relation_pair(
                        action.principle_node.literal,
                        action.path_node.literal,
                        fresh_variable=fresh_variable(),
                    )
                )
            elif (
                action.action_type == "extension"
                and action.clause_copy is not None
                and action.lit_idx is not None
                and action.principle_node.literal is not None
            ):
                equations.append(
                    self.relation_pair(
                        action.principle_node.literal,
                        action.clause_copy[action.lit_idx],
                        fresh_variable=fresh_variable(),
                    )
                )

        all_updates: List[SubstitutionUpdate] = []
        for left, right in equations:
            ok, updates = self.unify(left, right)
            if not ok:
                return False, []
            all_updates.extend(updates)
        return True, all_updates
