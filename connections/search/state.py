from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple

from connections.logic.prefix_substitution import PrefixSubstitution
from connections.logic.substitution import Substitution
from connections.logic.syntax import Clause, Literal, Variable
from connections.logic.tableau import Tableau
from connections.search.actions import Action
from connections.utils.factories import ClauseFactory, VarFactory


class SettingsLike(Protocol):
    positive_start_clauses: bool
    iterative_deepening: bool
    iterative_deepening_initial_depth: int
    logic: str
    domain: str


class State:
    def __init__(self, matrix: Any, settings: SettingsLike) -> None:
        self.matrix = matrix
        self.settings = settings
        self.clause_factory = ClauseFactory()
        self.prefix_var_factory = VarFactory()
        self.prefix_substitution = PrefixSubstitution(
            logic=settings.logic,
            domain=settings.domain,
        )
        self.prefix_unifier: Dict[Any, Any] = {}
        self.reset()

    def __str__(self) -> str:
        substitution = "\n".join(
            f"{k} -> {v}" for k, v in self.substitution.to_dict().items()
        )
        actions = []
        if self.goal is not None:
            actions = [str(action) for action in self.goal.actions.values()]
        return (
            "=========================\n"
            f"Tableau:\n{self.tableau}\n"
            f"Substitution:\n{substitution}\n"
            f"Available Actions:\n{actions}\n"
            f"Max Depth: {self.max_depth}\n"
            "========================="
        )

    @property
    def action_space(self) -> list[Any]:
        if self.goal is None:
            return [None]
        raw_actions = self.goal.actions
        if isinstance(raw_actions, dict):
            actions = list(raw_actions.values())
        else:
            actions = list(raw_actions)
        return actions if actions else [None]

    def reset(self, depth: Optional[int] = None) -> None:
        self.max_depth = depth
        if self.max_depth is None:
            self.max_depth = self.settings.iterative_deepening_initial_depth
        self.tableau = Tableau()
        self.tableau.literal = None
        self.tableau.actions = {}
        self.substitution = Substitution()
        self.proof_sequence: List[Action] = []
        self.info: Optional[str] = None
        self.is_terminal = False
        self.goal: Optional[Tableau] = None
        self._refresh_goal()

    def _node_closed(self, node: Tableau) -> bool:
        if node.children:
            return node.closed_branches >= len(node.children)
        return node.closed_branches > 0

    def _extend_path(self, node: Tableau) -> Dict[Tuple[bool, str], List[Tableau]]:
        base: Dict[Tuple[bool, str], List[Tableau]] = {}
        if node.path is not None:
            for key, value in node.path.items():
                base[key] = list(value)
        if node.literal is not None:
            key = (node.literal.neg, node.literal.name)
            base.setdefault(key, []).append(node)
        return base

    def _find_open_goal(self, node: Tableau) -> Optional[Tableau]:
        if self._node_closed(node):
            return None
        if not node.children:
            return None if node.path is None else node
        for child in node.children:
            goal = self._find_open_goal(child)
            if goal is not None:
                return goal
        return None

    def _starts(self, node: Tableau) -> List[Action]:
        candidates = range(len(self.matrix.clauses))
        if self.settings.positive_start_clauses:
            candidates = self.matrix.positive_clauses
        actions: List[Action] = []
        for index, clause_idx in enumerate(candidates):
            clause: Clause = self.matrix[clause_idx]
            clause_copy = self.clause_factory.freshen_clause(clause)
            actions.append(
                Action(
                    action_type="start",
                    id=f"st{index}",
                    principle_node=node,
                    clause_idx=clause_idx,
                    clause_copy=clause_copy,
                )
            )
        return actions

    def _extensions(self, node: Tableau) -> List[Action]:
        if node.literal is None:
            return []
        actions: List[Action] = []
        for clause_idx, lit_idx in self.matrix.complements(node.literal):
            clause: Clause = self.matrix[clause_idx]
            clause_copy = self.clause_factory.freshen_clause(clause)
            target_lit = clause_copy[lit_idx]
            ok, updates = self.substitution.can_unify(node.literal, target_lit)
            if not ok:
                continue
            if not self.prefix_substitution.relation_ok(
                node.literal,
                target_lit,
                self.substitution,
                updates,
                self._next_prefix_variable,
            ):
                continue
            action_id = f"ex{len(actions)}"
            actions.append(
                Action(
                    action_type="extension",
                    id=action_id,
                    principle_node=node,
                    clause_idx=clause_idx,
                    lit_idx=lit_idx,
                    clause_copy=clause_copy,
                    sub_updates=updates,
                )
            )
        return actions

    def _reductions(self, node: Tableau) -> List[Action]:
        if node.path is None or node.literal is None:
            return []
        key = (not node.literal.neg, node.literal.name)
        path_nodes = node.path.get(key, [])
        actions: List[Action] = []
        for path_node in path_nodes:
            if path_node.literal is None:
                continue
            ok, updates = self.substitution.can_unify(node.literal, path_node.literal)
            if not ok:
                continue
            if not self.prefix_substitution.relation_ok(
                node.literal,
                path_node.literal,
                self.substitution,
                updates,
                self._next_prefix_variable,
            ):
                continue
            action_id = f"re{len(actions)}"
            actions.append(
                Action(
                    action_type="reduction",
                    id=action_id,
                    principle_node=node,
                    path_node=path_node,
                    sub_updates=updates,
                )
            )
        return actions

    def _legal_actions(self, node: Tableau) -> Dict[str, Action]:
        if node.path is None:
            return {action.id: action for action in self._starts(node)}
        max_depth = self.max_depth if self.max_depth is not None else 0
        if self.settings.iterative_deepening and node.depth >= max_depth:
            actions = self._reductions(node)
        else:
            actions = self._reductions(node) + self._extensions(node)
        return {action.id: action for action in actions}

    def _refresh_goal(self) -> None:
        while True:
            root_actions = (
                self._legal_actions(self.tableau) if not self.tableau.children else {}
            )
            if not self.tableau.children:
                if not root_actions:
                    self.goal = None
                    self.is_terminal = True
                    self.info = "Non-Theorem: no positive start clauses"
                    return
                self.goal = self.tableau
                self.goal.actions = root_actions
                return

            if self.tableau.closed_branches >= len(self.tableau.children):
                if not self._prefix_proof_ok():
                    self.goal = None
                    self.is_terminal = True
                    self.info = "Non-Theorem"
                    return
                self.goal = None
                self.is_terminal = True
                self.info = "Theorem"
                return

            goal = self._find_open_goal(self.tableau)
            if goal is None:
                if not self._prefix_proof_ok():
                    self.goal = None
                    self.is_terminal = True
                    self.info = "Non-Theorem"
                    return
                self.goal = None
                self.is_terminal = True
                self.info = "Theorem"
                return

            actions = self._legal_actions(goal)
            if actions:
                self.goal = goal
                goal.actions = actions
                return

            goal.propogate_closed()

    def _expand_with_clause(
        self,
        node: Tableau,
        clause_idx: int,
        clause_copy: Tuple[Literal, ...],
        close_lit_idx: Optional[int],
    ) -> None:
        path = {} if node.path is None else self._extend_path(node)
        children: List[Tableau] = []
        for lit_idx, literal in enumerate(clause_copy):
            child = Tableau(
                literal_idx=(clause_idx, lit_idx),
                copy_num=0,
                path=path,
                parent=node,
            )
            child.literal = literal
            child.actions = {}
            children.append(child)
        node.children = children
        if close_lit_idx is not None:
            node.children[close_lit_idx].propogate_closed()

    def update_goal(self, action: Optional[Action]) -> None:
        if action is None:
            self._refresh_goal()
            return
        self.substitution.update(action.sub_updates)

        if action.action_type == "start":
            if action.clause_idx is None or action.clause_copy is None:
                return
            self._expand_with_clause(
                action.principle_node,
                action.clause_idx,
                action.clause_copy,
                close_lit_idx=None,
            )
        elif action.action_type == "extension":
            if action.clause_idx is None or action.clause_copy is None:
                return
            self._expand_with_clause(
                action.principle_node,
                action.clause_idx,
                action.clause_copy,
                close_lit_idx=action.lit_idx,
            )
        elif action.action_type == "reduction":
            action.principle_node.propogate_closed()

        self.proof_sequence.append(action)
        self._refresh_goal()

    def _next_prefix_variable(self) -> Variable:
        return self.prefix_var_factory.fresh("W")

    def _prefix_proof_ok(self) -> bool:
        result = self.prefix_substitution.proof_unifier(
            self.substitution,
            self.proof_sequence,
            self._next_prefix_variable,
        )
        if result is None:
            return False
        self.prefix_unifier = result.to_dict() if hasattr(result, "to_dict") else {}
        return True
