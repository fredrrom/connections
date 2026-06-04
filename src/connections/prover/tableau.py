from __future__ import annotations

from dataclasses import dataclass, field

from connections.core.matrix import Literal, SignedPredicateSymbol
from connections.prover.rules import Extension, Rule, Start


@dataclass(slots=True)
class RuleCache:
    target_gate: object | None = None
    rules: tuple[Rule, ...] = ()

    def current_rules(self, target_gate: object) -> tuple[Rule, ...] | None:
        return self.rules if self.target_gate == target_gate else None

    def replace(self, target_gate: object, rules: tuple[Rule, ...]) -> None:
        self.target_gate = target_gate
        self.rules = rules


@dataclass(slots=True)
class RuleApplication:
    rule_application_id: int
    parent_goal_id: int
    rule: Rule
    child_goal_ids: tuple[int, ...] = ()
    closed_child_goal_ids: tuple[int, ...] = ()


@dataclass(slots=True)
class TableauNode:
    goal_id: int
    parent_rule_application_id: int | None
    address: tuple[int, ...]
    literal_index: int | None = None
    clause_idx: int | None = None
    instance_id: int | None = None
    applied_rule_application_id: int | None = None
    depth: int = -1
    closed: bool = False
    path_goal_ids_by_signed_symbol: dict[SignedPredicateSymbol, tuple[int, ...]] = (
        field(default_factory=dict, repr=False)
    )
    factorization_source_goal_ids_by_signed_symbol: dict[
        SignedPredicateSymbol, tuple[int, ...]
    ] = field(default_factory=dict, repr=False)
    extension_cache: RuleCache = field(default_factory=RuleCache, repr=False)


class Tableau:
    def __init__(self):
        self.reset()

    @property
    def root(self) -> TableauNode:
        return self.goals[self.root_goal_id]

    def source_literal_at(self, goal: int | TableauNode) -> Literal | None:
        context = self.literal_context_at(goal)
        return None if context is None else context[0]

    def literal_context_at(
        self, goal: int | TableauNode
    ) -> tuple[Literal, int | None] | None:
        node = self.goals[goal] if isinstance(goal, int) else goal
        if (
            node.parent_rule_application_id is not None
            and node.literal_index is not None
        ):
            rule_application = self.rule_applications[node.parent_rule_application_id]
            rule = rule_application.rule
            if isinstance(rule, (Start, Extension)):
                return rule.clause.literal(node.literal_index), node.instance_id
        return None

    def reset(self) -> None:
        self.goals: dict[int, TableauNode] = {}
        self.rule_applications: dict[int, RuleApplication] = {}
        self.root_goal_id = 0
        self.next_goal_id = 1
        self.next_rule_application_id = 0
        self.goals[self.root_goal_id] = TableauNode(
            goal_id=self.root_goal_id,
            parent_rule_application_id=None,
            address=(),
            depth=-1,
        )

    def fresh_goal_id(self) -> int:
        goal_id = self.next_goal_id
        self.next_goal_id += 1
        return goal_id

    def fresh_rule_application_id(self) -> int:
        rule_application_id = self.next_rule_application_id
        self.next_rule_application_id += 1
        return rule_application_id

    def add_rule_application(
        self,
        *,
        parent_goal_id: int,
        rule: Rule,
        child_literal_indices: tuple[int, ...],
    ) -> RuleApplication:
        parent_goal = self.goals[parent_goal_id]
        if parent_goal.applied_rule_application_id is not None:
            raise ValueError("goal already has an applied rule application")

        rule_application_id = self.fresh_rule_application_id()
        child_goal_ids = self._create_child_goals(
            rule_application_id=rule_application_id,
            parent_goal_id=parent_goal_id,
            literal_indices=child_literal_indices,
            clause_idx=rule.clause_idx
            if isinstance(rule, (Start, Extension))
            else None,
            instance_id=rule.instance_id
            if isinstance(rule, (Start, Extension))
            else None,
            depth=parent_goal.depth + 1,
        )
        rule_application = RuleApplication(
            rule_application_id=rule_application_id,
            parent_goal_id=parent_goal_id,
            rule=rule,
            child_goal_ids=tuple(child_goal_ids),
        )
        self.rule_applications[rule_application_id] = rule_application
        parent_goal.applied_rule_application_id = rule_application_id
        return rule_application

    def remove_rule_application_subtree(
        self, rule_application_id: int
    ) -> tuple[tuple[int, ...], tuple[RuleApplication, ...]]:
        rule_application = self.rule_applications[rule_application_id]
        removed_goal_ids, removed_rule_applications = self._collect_subtree(
            rule_application_id
        )

        for removed_rule_application in removed_rule_applications:
            del self.rule_applications[removed_rule_application.rule_application_id]

        for removed_goal_id in removed_goal_ids:
            del self.goals[removed_goal_id]

        parent_goal = self.goals[rule_application.parent_goal_id]
        parent_goal.applied_rule_application_id = None
        return removed_goal_ids, removed_rule_applications

    def propagate_closedness_from(
        self, goal_id: int
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        reopened: list[int] = []
        changed_apps: list[int] = []
        current_goal_id: int | None = goal_id
        while current_goal_id is not None:
            goal = self.goals[current_goal_id]
            was_closed = goal.closed
            app_id = goal.applied_rule_application_id
            if app_id is None:
                goal.closed = False
            else:
                app = self.rule_applications[app_id]
                closed_child_goal_ids = tuple(
                    child_id
                    for child_id in app.child_goal_ids
                    if self.goals[child_id].closed
                )
                if app.closed_child_goal_ids != closed_child_goal_ids:
                    app.closed_child_goal_ids = closed_child_goal_ids
                    changed_apps.append(app_id)
                goal.closed = not app.child_goal_ids or len(
                    app.closed_child_goal_ids
                ) == len(app.child_goal_ids)
            if (
                was_closed
                and not goal.closed
                and self.source_literal_at(goal) is not None
            ):
                reopened.append(current_goal_id)
            parent_app_id = goal.parent_rule_application_id
            current_goal_id = (
                None
                if parent_app_id is None
                else self.rule_applications[parent_app_id].parent_goal_id
            )
        return tuple(reopened), tuple(changed_apps)

    def _create_child_goals(
        self,
        *,
        rule_application_id: int,
        parent_goal_id: int,
        literal_indices: tuple[int, ...],
        clause_idx: int | None,
        instance_id: int | None,
        depth: int,
    ) -> list[int]:
        child_goal_ids: list[int] = []
        parent_address = self.goals[parent_goal_id].address
        for child_position, literal_index in enumerate(literal_indices):
            child_goal_id = self.fresh_goal_id()
            self.goals[child_goal_id] = TableauNode(
                goal_id=child_goal_id,
                parent_rule_application_id=rule_application_id,
                address=(*parent_address, child_position),
                literal_index=literal_index,
                clause_idx=clause_idx,
                instance_id=instance_id,
                depth=depth,
            )
            child_goal_ids.append(child_goal_id)
        return child_goal_ids

    def _collect_subtree(
        self, rule_application_id: int
    ) -> tuple[tuple[int, ...], tuple[RuleApplication, ...]]:
        removed_goal_ids: list[int] = []
        removed_rule_applications: list[RuleApplication] = []

        def visit(current_rule_application_id: int) -> None:
            rule_application = self.rule_applications[current_rule_application_id]
            for child_goal_id in rule_application.child_goal_ids:
                removed_goal_ids.append(child_goal_id)
                child_goal = self.goals[child_goal_id]
                if child_goal.applied_rule_application_id is not None:
                    visit(child_goal.applied_rule_application_id)
            removed_rule_applications.append(rule_application)

        visit(rule_application_id)
        return tuple(removed_goal_ids), tuple(removed_rule_applications)

    def render_tableau(self) -> str:
        lines: list[str] = []

        def visit_goal(goal_id: int, indent: int) -> None:
            goal = self.goals[goal_id]
            prefix = "  " * indent
            literal = self.source_literal_at(goal)
            literal_text = "ROOT" if literal is None else str(literal)
            suffix = " closed" if goal.closed else ""
            lines.append(f"{prefix}{literal_text}{suffix}")

            rule_application_id = goal.applied_rule_application_id
            if rule_application_id is None:
                return

            rule_application = self.rule_applications[rule_application_id]
            lines.append(f"{prefix}  [{rule_application.rule!r}]")
            for child_goal_id in rule_application.child_goal_ids:
                visit_goal(child_goal_id, indent + 1)

        visit_goal(self.root_goal_id, 0)
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render_tableau()


__all__ = [
    "RuleApplication",
    "RuleCache",
    "Tableau",
    "TableauNode",
]
