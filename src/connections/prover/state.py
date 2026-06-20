from __future__ import annotations

from bisect import bisect_left
from typing import TYPE_CHECKING

from connections.syntax.matrix import Literal, SignedPredicateSymbol
from connections.constraints import ConstraintStore
from connections.prover.rules import (
    Extension,
    Rule,
    Start,
)
from connections.prover.tableau import (
    RuleApplication,
    Tableau,
    TableauNode,
)

if TYPE_CHECKING:
    from connections.prover.prover import Problem


class State:
    def __init__(self, problem: Problem, tableau: Tableau) -> None:
        self.problem = problem
        self.tableau = tableau
        self.reset()

    def reset(self) -> None:
        self.constraints = ConstraintStore()
        self.fringe = [self.tableau.root]
        self._next_instance_id = 1

    def source_literal_at(self, goal: int | TableauNode) -> Literal | None:
        return self.tableau.source_literal_at(goal)

    def literal_context_at(
        self, goal: int | TableauNode
    ) -> tuple[Literal, int | None] | None:
        return self.tableau.literal_context_at(goal)

    def fresh_instance_id(self) -> int:
        instance_id = self._next_instance_id
        self._next_instance_id += 1
        return instance_id

    def path_goal_ids_for(
        self, goal_id: int, symbol: SignedPredicateSymbol
    ) -> tuple[int, ...]:
        return self.tableau.goals[goal_id].path_goal_ids_by_signed_symbol.get(
            symbol, ()
        )

    def current_path_factorization_source_goal_ids_for(
        self, goal_id: int, symbol: SignedPredicateSymbol
    ) -> tuple[int, ...]:
        sources: list[int] = []
        current_goal_id: int | None = goal_id
        while current_goal_id is not None:
            goal = self.tableau.goals[current_goal_id]
            sources.extend(
                goal.factorization_source_goal_ids_by_signed_symbol.get(symbol, ())
            )
            parent_app_id = goal.parent_rule_application_id
            current_goal_id = (
                None
                if parent_app_id is None
                else self.tableau.rule_applications[parent_app_id].parent_goal_id
            )
        return tuple(sources)

    def apply_rule(
        self,
        *,
        parent_goal_id: int,
        rule: Rule,
    ) -> RuleApplication:
        rule_application = self.tableau.add_rule_application(
            parent_goal_id=parent_goal_id,
            rule=rule,
            child_literal_indices=self._child_literal_indices(rule),
        )
        self.constraints.commit(
            rule.constraint_delta,
            owner_app_id=rule_application.rule_application_id,
        )
        self._install_child_path_indices(rule_application)
        index = self._fringe_index(parent_goal_id)
        self.fringe[index : index + 1] = [
            self.tableau.goals[goal_id] for goal_id in rule_application.child_goal_ids
        ]
        if not rule_application.child_goal_ids:
            self._refresh_after_closedness_change(parent_goal_id)
        return rule_application

    @staticmethod
    def _child_literal_indices(rule: Rule) -> tuple[int, ...]:
        if isinstance(rule, Start):
            return tuple(range(rule.clause.literal_count))
        if isinstance(rule, Extension):
            return tuple(
                idx for idx in range(rule.clause.literal_count) if idx != rule.lit_idx
            )
        return ()

    def undo_rule_application(self, rule_application_id: int) -> None:
        rule_application = self.tableau.rule_applications[rule_application_id]
        removed_goal_ids, removed_apps = self.tableau.remove_rule_application_subtree(
            rule_application_id
        )
        self.constraints.rollback_owned_by(
            tuple(app.rule_application_id for app in removed_apps)
        )
        removed_goal_id_set = set(removed_goal_ids)
        self.fringe = [
            goal for goal in self.fringe if goal.goal_id not in removed_goal_id_set
        ]
        self._insert_open_leaf(rule_application.parent_goal_id)
        self._refresh_after_closedness_change(rule_application.parent_goal_id)

    def _refresh_after_closedness_change(self, goal_id: int) -> tuple[int, ...]:
        reopened, refreshed_apps = self.tableau.propagate_closedness_from(goal_id)
        for app_id in refreshed_apps:
            self._refresh_factorization_sources(self.tableau.rule_applications[app_id])
        return reopened

    def _install_child_path_indices(self, app: RuleApplication) -> None:
        path_index = dict(
            self.tableau.goals[app.parent_goal_id].path_goal_ids_by_signed_symbol
        )
        parent_literal = self.source_literal_at(app.parent_goal_id)
        if parent_literal is not None:
            path_index[parent_literal.signed_symbol] = (
                app.parent_goal_id,
                *path_index.get(parent_literal.signed_symbol, ()),
            )
        for child_goal_id in app.child_goal_ids:
            self.tableau.goals[child_goal_id].path_goal_ids_by_signed_symbol = dict(
                path_index
            )

    def _refresh_factorization_sources(self, app: RuleApplication) -> None:
        local: dict[SignedPredicateSymbol, list[int]] = {}
        for source_id in app.closed_child_goal_ids:
            literal = self.source_literal_at(source_id)
            if literal is not None:
                local.setdefault(literal.signed_symbol, []).append(source_id)
        for child_id in app.child_goal_ids:
            sources = {
                symbol: tuple(id_ for id_ in ids if id_ != child_id)
                for symbol, ids in local.items()
            }
            self._set_factorization_sources(
                child_id, {k: v for k, v in sources.items() if v}
            )

    def _set_factorization_sources(
        self, goal_id: int, sources: dict[SignedPredicateSymbol, tuple[int, ...]]
    ) -> None:
        goal = self.tableau.goals[goal_id]
        if goal.factorization_source_goal_ids_by_signed_symbol == sources:
            return
        goal.factorization_source_goal_ids_by_signed_symbol = dict(sources)

    def _insert_open_leaf(self, goal_id: int) -> None:
        goal = self.tableau.goals[goal_id]
        addresses = [node.address for node in self.fringe]
        self.fringe.insert(bisect_left(addresses, goal.address), goal)

    def _fringe_index(self, goal_id: int) -> int:
        for index, goal in enumerate(self.fringe):
            if goal.goal_id == goal_id:
                return index
        raise ValueError(f"goal is not in fringe: {goal_id}")


__all__ = ["State"]
