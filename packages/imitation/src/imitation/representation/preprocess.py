"""Live state -> GraphInput: the percept serialized for the model.

The percept is already [s, omega]: the state carries its matrix, so the
static tier comes from the state itself and the goal tier is rebuilt per
decision. Proof-replay tableaux hold only proof steps, so the overlay is
tens of nodes and the cost is dwarfed by the model call; incremental
maintenance is an inference-time optimization layered on later without
changing the schema. The ``start`` mode is part of the preprocessor because
it changes the start-clause feature, and with it the surface.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar, Literal as LiteralType

from connections.environment.actions import Action, ApplyAction, UndoAction
from connections.environment.dynamics import start_clause_ids
from connections.environment.rules import Extension, Factorization, Reduction, Start
from connections.environment.state import State
from connections.environment.tableau import Tableau

from imitation.representation.matrix import matrix_graph
from imitation.representation.schema import (
    ACTION_KINDS,
    ACTION_TARGET_TYPES,
    GraphInput,
)

_KIND = {name: index for index, name in enumerate(ACTION_KINDS)}
_TARGET = {name: index for index, name in enumerate(ACTION_TARGET_TYPES)}


@dataclass(frozen=True, slots=True)
class GraphPreprocessor:
    """Serialize a live state and its candidate actions into a graph."""

    name: ClassVar[str] = "graph"
    version: ClassVar[str] = "1"

    start: LiteralType["positive", "conjecture"] = "positive"

    def __call__(self, state: State, actions: Sequence[Action]) -> GraphInput:
        static = matrix_graph(state.matrix, start_clause_ids(state.matrix, self.start))
        tableau = state.tableau

        goal_index: dict[int, int] = {}
        goal_nodes: list[list[int]] = []
        for goal_id in tableau.goals:
            goal = tableau.goals[goal_id]
            goal_index[goal_id] = len(goal_nodes)
            goal_nodes.append(
                [
                    int(not goal.closed),
                    min(max(goal.depth, 0), 7),
                ]
            )

        edges: dict[str, list[list[int]]] = {
            name: list(rows) for name, rows in static.edges.items()
        }
        edges["instance_of"] = []
        edges["parent"] = []
        edges["path"] = []

        parent_of: dict[int, int] = {}
        for goal_id, goal in tableau.goals.items():
            local = goal_index[goal_id]
            if goal.clause_idx is not None and goal.literal_index is not None:
                edges["instance_of"].append(
                    [
                        local,
                        static.literal_index[(goal.clause_idx, goal.literal_index)],
                    ]
                )
            app_id = goal.parent_rule_application_id
            if app_id is not None:
                app = tableau.rule_applications.get(app_id)
                if app is not None:
                    parent_of[goal_id] = app.parent_goal_id
                    edges["parent"].append([local, goal_index[app.parent_goal_id]])

        # Every ancestor one hop from each open goal: edges mirror reductions.
        for goal_id, goal in tableau.goals.items():
            if goal.closed or goal.applied_rule_application_id is not None:
                continue
            ancestor = parent_of.get(goal_id)
            while ancestor is not None:
                edges["path"].append([goal_index[ancestor], goal_index[goal_id]])
                ancestor = parent_of.get(ancestor)

        action_rows = [
            _action_row(action, tableau, static.literal_index, goal_index)
            for action in actions
        ]

        nodes = {name: list(rows) for name, rows in static.nodes.items()}
        nodes["goal"] = goal_nodes
        return GraphInput(
            nodes=nodes,
            edges=edges,
            actions=action_rows,
            metadata={
                "goal_count": len(goal_nodes),
                "action_count": len(action_rows),
                # In-process identity of the static tier: lets the action
                # model reuse frozen matrix embeddings across decisions.
                "matrix_key": static.key,
            },
        )


def _action_row(
    action: Action,
    tableau: Tableau,
    literal_index: dict[tuple[int, int], int],
    goal_index: dict[int, int],
) -> list[int]:
    if isinstance(action, UndoAction):
        app = tableau.rule_applications[action.step_id]
        return [
            _KIND["backtrack"],
            goal_index[app.parent_goal_id],
            _TARGET["none"],
            0,
        ]
    if not isinstance(action, ApplyAction):
        raise TypeError(f"unsupported action: {action!r}")
    source = goal_index[action.goal_id]
    rule = action.rule
    if isinstance(rule, Start):
        if rule.clause_idx is None:
            return [_KIND["start"], source, _TARGET["none"], 0]
        return [_KIND["start"], source, _TARGET["clause"], rule.clause_idx]
    if isinstance(rule, Extension):
        if rule.clause_idx is None:
            return [_KIND["extension"], source, _TARGET["none"], 0]
        return [
            _KIND["extension"],
            source,
            _TARGET["literal"],
            literal_index[(rule.clause_idx, rule.lit_idx)],
        ]
    if isinstance(rule, Reduction):
        return [
            _KIND["reduction"],
            source,
            _TARGET["goal"],
            goal_index[rule.source_goal_id],
        ]
    if isinstance(rule, Factorization):
        return [
            _KIND["factorization"],
            source,
            _TARGET["goal"],
            goal_index[rule.source_goal_id],
        ]
    raise TypeError(f"unsupported rule: {rule!r}")


__all__ = ["GraphPreprocessor"]
