from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple

from connections.logic.substitution import (
    PrefixSubstitution,
    SubstitutionUpdate,
    TermSubstitution,
)
from connections.logic.syntax import Clause, Variable
from connections.logic.tableau import Tableau
from connections.utils.factories import ClauseFactory, VarFactory


@dataclass
class DecisionRecord:
    action_type: str
    term_updates: List[SubstitutionUpdate] = field(default_factory=list)
    sequence: int = 0


class State:
    def __init__(self, matrix: Any, settings: Any) -> None:
        self.matrix = matrix
        self.settings = settings
        self.clause_factory = ClauseFactory()
        self.prefix_var_factory = VarFactory()

        self.term_substitution = TermSubstitution()
        self.prefix_substitution = PrefixSubstitution(
            logic=settings.logic,
            domain=settings.domain,
            term_substitution=self.term_substitution,
        )

        self.tableau = Tableau()
        self.decision_by_node_id: Dict[int, DecisionRecord] = {}
        self.next_decision_sequence = 0

        self.info: Optional[str] = None
        self.is_terminal = False

    def __str__(self) -> str:
        return (
            "=========================\n"
            f"Tableau:\n{self.tableau}\n"
            f"Term Substitution:\n{self.term_substitution}\n"
            f"Prefix Substitution:\n{self.prefix_substitution}\n"
            "========================="
        )

    def _next_prefix_variable(self) -> Variable:
        return self.prefix_var_factory.fresh("W")

    def _record_decision(
        self,
        node_id: int,
        action_type: str,
        term_updates: List[SubstitutionUpdate],
    ) -> None:
        self.next_decision_sequence += 1
        self.decision_by_node_id[node_id] = DecisionRecord(
            action_type=action_type,
            term_updates=list(term_updates),
            sequence=self.next_decision_sequence,
        )

    def has_decision(self, node_id: int) -> bool:
        return node_id in self.decision_by_node_id

    def collect_fringe_node_ids(self) -> Set[int]:
        self.tableau.recompute_closed_branches()
        return set(self.tableau.open_goal_ids())

    def _extend_path(self, node: Tableau) -> Dict[Tuple[bool, str], List[Tableau]]:
        base: Dict[Tuple[bool, str], List[Tableau]] = {}
        if node.path is not None:
            for key, value in node.path.items():
                base[key] = list(value)
        if node.literal is not None:
            key = (node.literal.neg, node.literal.name)
            base.setdefault(key, []).append(node)
        return base

    def legal_action_specs(self, node_id: int) -> List[Dict[str, Any]]:
        node = self.tableau.get_node(node_id)
        if node is None:
            return []
        if node.path is None:
            return self._start_specs()
        return self._reduction_specs(node) + self._extension_specs(node)

    def _start_specs(self) -> List[Dict[str, Any]]:
        candidates = range(len(self.matrix.clauses))
        if self.settings.positive_start_clauses:
            candidates = self.matrix.positive_clauses
        specs: List[Dict[str, Any]] = []
        for index, clause_idx in enumerate(candidates):
            clause: Clause = self.matrix[clause_idx]
            clause_copy = self.clause_factory.freshen_clause(clause)
            specs.append(
                {
                    "kind": "start",
                    "suffix": f"st{index}",
                    "clause_idx": clause_idx,
                    "clause_copy": clause_copy,
                }
            )
        return specs

    def _extension_specs(self, node: Tableau) -> List[Dict[str, Any]]:
        if node.literal is None:
            return []
        specs: List[Dict[str, Any]] = []
        for clause_idx, lit_idx in self.matrix.complements(node.literal):
            clause: Clause = self.matrix[clause_idx]
            clause_copy = self.clause_factory.freshen_clause(clause)
            target_lit = clause_copy[lit_idx]
            ok, term_updates = self.term_substitution.unify(node.literal, target_lit)
            if not ok:
                continue
            if not self.prefix_substitution.relation_ok(
                node.literal,
                target_lit,
                self.term_substitution,
                term_updates,
                self._next_prefix_variable,
            ):
                continue
            specs.append(
                {
                    "kind": "extension",
                    "suffix": f"ex{len(specs)}",
                    "clause_idx": clause_idx,
                    "lit_idx": lit_idx,
                    "clause_copy": clause_copy,
                    "term_updates": term_updates,
                }
            )
        return specs

    def _reduction_specs(self, node: Tableau) -> List[Dict[str, Any]]:
        if node.path is None or node.literal is None:
            return []
        key = (not node.literal.neg, node.literal.name)
        path_nodes = node.path.get(key, [])
        specs: List[Dict[str, Any]] = []
        for path_node in path_nodes:
            if path_node.literal is None:
                continue
            ok, term_updates = self.term_substitution.unify(
                node.literal, path_node.literal
            )
            if not ok:
                continue
            if not self.prefix_substitution.relation_ok(
                node.literal,
                path_node.literal,
                self.term_substitution,
                term_updates,
                self._next_prefix_variable,
            ):
                continue
            specs.append(
                {
                    "kind": "reduction",
                    "suffix": f"re{len(specs)}",
                    "path_node_id": self.tableau.get_node_id(path_node),
                    "term_updates": term_updates,
                }
            )
        return specs

    def apply_start(self, node_id: int, clause_idx: int) -> bool:
        node = self.tableau.get_node(node_id)
        if node is None:
            return False
        if node.path is not None:
            return False
        clause: Clause = self.matrix[clause_idx]
        clause_copy = self.clause_factory.freshen_clause(clause)
        children: List[Tableau] = []
        for lit_idx, literal in enumerate(clause_copy):
            child = Tableau(
                literal_idx=(clause_idx, lit_idx),
                copy_num=0,
                path={},
                parent=node,
            )
            child.literal = literal
            children.append(child)
        node.children = children
        self._record_decision(node_id, "start", [])
        return True

    def apply_extension(self, node_id: int, clause_idx: int, lit_idx: int) -> bool:
        node = self.tableau.get_node(node_id)
        if node is None:
            return False
        if node.literal is None:
            return False
        clause: Clause = self.matrix[clause_idx]
        clause_copy = self.clause_factory.freshen_clause(clause)
        if lit_idx < 0 or lit_idx >= len(clause_copy):
            return False
        target_lit = clause_copy[lit_idx]
        ok, term_updates = self.term_substitution.unify(node.literal, target_lit)
        if not ok:
            return False
        if not self.prefix_substitution.relation_ok(
            node.literal,
            target_lit,
            self.term_substitution,
            term_updates,
            self._next_prefix_variable,
        ):
            return False

        self.term_substitution.update(term_updates)
        path = self._extend_path(node)
        children: List[Tableau] = []
        for new_lit_idx, literal in enumerate(clause_copy):
            child = Tableau(
                literal_idx=(clause_idx, new_lit_idx),
                copy_num=0,
                path=path,
                parent=node,
            )
            child.literal = literal
            children.append(child)
        node.children = children
        node.children[lit_idx].propogate_closed()
        self._record_decision(node_id, "extension", term_updates)
        return True

    def apply_reduction(self, node_id: int, path_node_id: int) -> bool:
        node = self.tableau.get_node(node_id)
        path_node = self.tableau.get_node(path_node_id)
        if node is None or path_node is None:
            return False
        if node.literal is None or path_node.literal is None:
            return False
        ok, term_updates = self.term_substitution.unify(node.literal, path_node.literal)
        if not ok:
            return False
        if not self.prefix_substitution.relation_ok(
            node.literal,
            path_node.literal,
            self.term_substitution,
            term_updates,
            self._next_prefix_variable,
        ):
            return False

        self.term_substitution.update(term_updates)
        node.propogate_closed()
        self._record_decision(node_id, "reduction", term_updates)
        return True

    def cut_decision(self, node_id: int) -> None:
        node = self.tableau.get_node(node_id)
        if node is None or node_id not in self.decision_by_node_id:
            return

        affected_nodes: List[Tableau] = []

        def visit(current: Tableau) -> None:
            affected_nodes.append(current)
            for child in current.children:
                visit(child)

        visit(node)

        decided_nodes = [
            n for n in affected_nodes if n.node_id() in self.decision_by_node_id
        ]
        decided_nodes.sort(
            key=lambda n: self.decision_by_node_id[n.node_id()].sequence,
            reverse=True,
        )
        for decided in decided_nodes:
            record = self.decision_by_node_id.pop(decided.node_id())
            self.term_substitution.revert(record.term_updates)

        for child in node.children:
            child.remove_subtree_from_index()
        node.children = []
        node.closed_branches = 0
        self.tableau.recompute_closed_branches()

    def evaluate_terminal(self, fringe_node_ids: Set[int]) -> None:
        if fringe_node_ids:
            self.is_terminal = False
            self.info = None
            return

        self.tableau.recompute_closed_branches()
        if self.tableau.children and self.tableau.is_closed():
            if self._prefix_proof_ok():
                self.is_terminal = True
                self.info = "Theorem"
            else:
                self.is_terminal = True
                self.info = "Non-Theorem"
            return

        if not self.tableau.children:
            self.is_terminal = True
            self.info = "Non-Theorem: no positive start clauses"
            return

        self.is_terminal = True
        self.info = "Non-Theorem"

    def _prefix_proof_ok(self) -> bool:
        proof_actions = self._proof_actions(self.tableau)
        ok, prefix_updates = self.prefix_substitution.proof_unifier(
            self.term_substitution,
            proof_actions,
            self._next_prefix_variable,
        )
        if not ok:
            return False
        self.prefix_substitution.update(prefix_updates)
        return True

    def _proof_actions(self, node: Tableau) -> List[Any]:
        actions: List[Any] = []
        record = self.decision_by_node_id.get(node.node_id())
        if record is not None and record.action_type in {"extension", "reduction"}:
            action_like = SimpleNamespace(
                action_type=record.action_type,
                principle_node=node,
            )
            if record.action_type == "reduction":
                action_like.path_node = self._find_reduction_partner(node)
            else:
                action_like.clause_copy = tuple(
                    child.literal for child in node.children
                )
                action_like.lit_idx = self._closed_child_idx(node)
            actions.append(action_like)
        for child in node.children:
            actions.extend(self._proof_actions(child))
        return actions

    def _find_reduction_partner(self, node: Tableau) -> Optional[Tableau]:
        if node.path is None or node.literal is None:
            return None
        key = (not node.literal.neg, node.literal.name)
        for path_node in node.path.get(key, []):
            if path_node.literal is not None:
                return path_node
        return None

    def _closed_child_idx(self, node: Tableau) -> int:
        for idx, child in enumerate(node.children):
            if child.is_closed():
                return idx
        return 0
