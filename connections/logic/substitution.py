from typing import Any, Dict, Iterable, List, Tuple

from connections.logic.syntax import Literal, Prefix, Term, Variable


class Substitution:
    """Single-assignment substitution with scoped rollback."""

    def __init__(self) -> None:
        self.bindings: Dict[Variable, Any] = {}

    def find(self, term: Any) -> Any:
        while isinstance(term, Variable) and term in self.bindings:
            term = self.bindings[term]
        return term

    def occurs(self, var: Variable, term: Any) -> bool:
        term = self.find(term)
        if var == term:
            return True
        if isinstance(term, Prefix):
            return any(self.occurs(var, part) for part in term.parts)
        if isinstance(term, (Term, Literal)):
            if any(self.occurs(var, arg) for arg in term.args):
                return True
            if term.prefix is not None:
                return self.occurs(var, term.prefix)
        return False

    def _bind(
        self, var: Variable, term: Any, updates: List[Tuple[Variable, Any]]
    ) -> bool:
        if var in self.bindings:
            return False
        self.bindings[var] = term
        updates.append((var, term))
        return True

    def unify(
        self, s: Any, t: Any, apply: bool = True
    ) -> Tuple[bool, List[Tuple[Variable, Any]]]:
        updates: List[Tuple[Variable, Any]] = []
        ok = self._unify_terms(s, t, updates)
        if not ok:
            self.cut(updates)
            return False, []
        if not apply:
            self.cut(updates)
        return True, updates

    def can_unify(self, s: Any, t: Any) -> Tuple[bool, List[Tuple[Variable, Any]]]:
        return self.unify(s, t, apply=False)

    def _unify_terms(self, s: Any, t: Any, updates: List[Tuple[Variable, Any]]) -> bool:
        equations = [(s, t)]
        while equations:
            s, t = equations.pop()
            s = self.find(s)
            t = self.find(t)

            if s == t:
                continue

            if isinstance(s, Variable) and isinstance(t, Variable):
                if self.occurs(s, t) or self.occurs(t, s):
                    return False
                var, term = (t, s) if s.vid < t.vid else (s, t)
                if not self._bind(var, term, updates):
                    return False
                continue

            if isinstance(s, Variable):
                if self.occurs(s, t):
                    return False
                if not self._bind(s, t, updates):
                    return False
                continue

            if isinstance(t, Variable):
                if self.occurs(t, s):
                    return False
                if not self._bind(t, s, updates):
                    return False
                continue

            if isinstance(s, Prefix) and isinstance(t, Prefix):
                if len(s.parts) != len(t.parts):
                    return False
                for part_s, part_t in zip(s.parts, t.parts):
                    equations.append((part_s, part_t))
                continue

            if not isinstance(s, (Term, Literal)) or not isinstance(t, (Term, Literal)):
                return False
            if s.name != t.name or len(s.args) != len(t.args):
                return False
            for arg1, arg2 in zip(s.args, t.args):
                equations.append((arg1, arg2))
            if s.prefix is None and t.prefix is None:
                continue
            if s.prefix is None or t.prefix is None:
                return False
            equations.append((s.prefix, t.prefix))
        return True

    def update(self, updates: List[Tuple[Variable, Any]]) -> None:
        for var, term in updates:
            if var not in self.bindings:
                self.bindings[var] = term

    def cut(self, terms: Iterable[Any]) -> None:
        removed_vars: List[Variable] = []
        for item in terms:
            if isinstance(item, tuple) and item and isinstance(item[0], Variable):
                removed_vars.append(item[0])
            elif isinstance(item, Variable):
                removed_vars.append(item)
        if not removed_vars:
            return
        removed_set = set(removed_vars)
        for var in removed_vars:
            if var in self.bindings:
                del self.bindings[var]
        dangling = [var for var, term in self.bindings.items() if term in removed_set]
        for var in dangling:
            if var in self.bindings:
                del self.bindings[var]

    def equal(self, s: Any, t: Any) -> bool:
        s = self.find(s)
        t = self.find(t)
        if s == t:
            return True
        if isinstance(s, Prefix) and isinstance(t, Prefix):
            return len(s.parts) == len(t.parts) and all(
                self.equal(a, b) for a, b in zip(s.parts, t.parts)
            )
        if isinstance(s, (Term, Literal)) and isinstance(t, (Term, Literal)):
            return (
                s.name == t.name
                and len(s.args) == len(t.args)
                and all(self.equal(a, b) for a, b in zip(s.args, t.args))
                and (
                    (s.prefix is None and t.prefix is None)
                    or (
                        s.prefix is not None
                        and t.prefix is not None
                        and self.equal(s.prefix, t.prefix)
                    )
                )
            )
        return False

    def __call__(self, term: Any) -> Any:
        term = self.find(term)
        if isinstance(term, Prefix):
            return Prefix(tuple(self(part) for part in term.parts))
        if isinstance(term, Variable):
            return term
        if isinstance(term, Term):
            args = tuple(self(arg) for arg in term.args)
            prefix = self(term.prefix) if term.prefix is not None else None
            return type(term)(term.name, args=args, prefix=prefix)
        if isinstance(term, Literal):
            args = tuple(self(arg) for arg in term.args)
            prefix = self(term.prefix) if term.prefix is not None else None
            return Literal(term.name, args=args, prefix=prefix, neg=term.neg)
        return term

    def to_dict(self) -> Dict[Variable, Any]:
        return {var: self.find(term) for var, term in self.bindings.items()}

    def __repr__(self) -> str:
        return repr(self.to_dict())
