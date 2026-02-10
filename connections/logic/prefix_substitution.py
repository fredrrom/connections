from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from connections.logic.substitution import Substitution
from connections.logic.syntax import Function, Prefix, Variable


@dataclass
class PrefixSubstitution:
    logic: str = "intuitionistic"
    domain: str = "constant"
    bindings: Dict[Variable, Prefix] = field(default_factory=dict)

    def normalize(self, prefix: Prefix) -> Prefix:
        if self.logic == "S5":
            if not prefix.parts:
                return prefix
            return Prefix((prefix.parts[-1],))
        return prefix

    def is_active(self) -> bool:
        return self.logic != "classical"

    def should_collect_admissible_pairs(self) -> bool:
        if self.logic == "classical":
            return False
        if self.logic == "D" and self.domain == "constant":
            return False
        if self.logic == "T" and self.domain == "constant":
            return False
        if self.logic == "S4" and self.domain == "constant":
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
        raise TypeError(f"Unsupported prefix value: {type(value)!r}")

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

        if self.logic == "S5":
            if self.domain == "varying":
                left_last = Prefix(left.parts[-1:]) if left.parts else Prefix(())
                right_last = Prefix(right.parts[-1:]) if right.parts else Prefix(())
                return left_last, right_last
            return None

        return left, right

    def eigenvariables(self, term: Any) -> List[Any]:
        if isinstance(term, Function) and term.name == "f_skolem":
            return [term]
        if isinstance(term, Function):
            found: List[Any] = []
            for subterm in term.args:
                found.extend(self.eigenvariables(subterm))
            return found
        return []

    def unify(
        self,
        pre_1: Any,
        pre_2: Any,
        term_substitution: Substitution,
    ) -> Optional[Substitution]:
        p1 = self._as_prefix(pre_1)
        p2 = self._as_prefix(pre_2)
        ok, _ = term_substitution.can_unify(p1, p2)
        return term_substitution if ok else None

    def unify_pairs(
        self,
        prefix_list: List[Tuple[Any, Any]],
        term_substitution: Substitution,
    ) -> Optional[Substitution]:
        for left, right in prefix_list:
            if self.unify(left, right, term_substitution) is None:
                return None
        return term_substitution

    def relation_ok(
        self,
        left_literal: Any,
        right_literal: Any,
        term_substitution: Substitution,
        sub_updates: List[Tuple[Any, Any]],
        fresh_variable: Callable[[], Variable],
    ) -> bool:
        if not self.is_active():
            return True
        left_prefix, right_prefix = self.relation_pair(
            left_literal,
            right_literal,
            fresh_variable=fresh_variable(),
        )
        term_substitution.update(sub_updates)
        result = self.unify(left_prefix, right_prefix, term_substitution)
        term_substitution.cut(sub_updates)
        return result is not None

    def admissible_pairs(
        self,
        term_substitution: Substitution,
        fresh_variable: Callable[[], Variable],
    ) -> List[Tuple[Prefix, Prefix]]:
        if not self.should_collect_admissible_pairs():
            return []
        equations: List[Tuple[Prefix, Prefix]] = []
        for var, term in term_substitution.to_dict().items():
            var_prefix = var.prefix if var.prefix is not None else Prefix(())
            for eigen in self.eigenvariables(term):
                eigen_prefix = eigen.prefix if eigen.prefix is not None else Prefix(())
                pair = self.admissible_pair(
                    var_prefix,
                    eigen_prefix,
                    fresh_variable=fresh_variable(),
                )
                if pair is not None:
                    equations.append(pair)
        return equations

    def proof_pairs(
        self,
        proof_sequence: List[Any],
        fresh_variable: Callable[[], Variable],
    ) -> List[Tuple[Prefix, Prefix]]:
        if not self.is_active():
            return []
        equations: List[Tuple[Prefix, Prefix]] = []
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
        return equations

    def proof_unifier(
        self,
        term_substitution: Substitution,
        proof_sequence: List[Any],
        fresh_variable: Callable[[], Variable],
    ) -> Optional[Substitution]:
        if not self.is_active():
            return term_substitution
        pairs = self.admissible_pairs(
            term_substitution, fresh_variable
        ) + self.proof_pairs(
            proof_sequence,
            fresh_variable,
        )
        return self.unify_pairs(pairs, term_substitution)
