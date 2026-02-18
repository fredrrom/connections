from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple, Union
from connections.search.actions import Action
from connections.search.state import State

LogicType = Literal["classical", "intuitionistic", "D", "T", "S4", "S5"]
DomainType = Literal["constant", "cumulative", "varying"]


@dataclass(frozen=True)
class Settings:
    positive_start_clauses: bool = True
    restricted_backtracking: bool = False
    backtrack_after: int = 2
    logic: LogicType = "classical"
    domain: DomainType = "constant"


class ConnectionEnv:
    def __init__(
        self, path: Union[str, Path], settings: Optional[Settings] = None
    ) -> None:
        self.path = str(path)
        self.settings = settings or Settings()
        self.matrix = self._parse_matrix(self.path)
        self.state = State(self.matrix, self.settings)

        self.fringe_node_ids: set[int] = set()
        self.available_actions_by_goal: Dict[int, Dict[str, Action]] = {}
        self._refresh_indexes_and_actions(invalidate_all=True)

    def _parse_matrix(self, path: str) -> Any:
        if self.settings.logic == "classical":
            from connections.utils.cnf_parsing import file2cnf
        else:
            from connections.utils.icnf_parsing import file2cnf
        return file2cnf(path)

    def _make_action(self, node_id: int, spec: Dict[str, Any]) -> Action:
        kind = spec["kind"]
        suffix = spec["suffix"]
        action_id = f"{node_id}:{suffix}"
        if kind == "start":
            return Action(
                action_type="start",
                id=action_id,
                node_id=node_id,
                clause_idx=spec["clause_idx"],
                clause_copy=spec.get("clause_copy"),
            )
        if kind == "extension":
            return Action(
                action_type="extension",
                id=action_id,
                node_id=node_id,
                clause_idx=spec["clause_idx"],
                lit_idx=spec["lit_idx"],
                clause_copy=spec.get("clause_copy"),
                sub_updates=spec.get("term_updates", []),
            )
        if kind == "reduction":
            path_node_id = spec.get("path_node_id")
            return Action(
                action_type="reduction",
                id=action_id,
                node_id=node_id,
                path_node_id=path_node_id,
                sub_updates=spec.get("term_updates", []),
            )
        raise ValueError(f"Unknown action kind: {kind}")

    def _refresh_indexes_and_actions(self, invalidate_all: bool) -> None:
        while True:
            new_fringe_ids = self.state.collect_fringe_node_ids()

            if invalidate_all:
                self.available_actions_by_goal = {}
                invalidate_all = False

            for stale_goal_id in list(self.available_actions_by_goal.keys()):
                if stale_goal_id not in new_fringe_ids:
                    self.available_actions_by_goal.pop(stale_goal_id, None)

            progress = False
            for node_id in sorted(new_fringe_ids):
                specs = self.state.legal_action_specs(node_id)
                by_id: Dict[str, Action] = {}
                for spec in specs:
                    action = self._make_action(node_id, spec)
                    by_id[action.id] = action
                if self.state.has_decision(node_id):
                    cut_id = f"{node_id}:cut"
                    by_id[cut_id] = Action(
                        action_type="cut_decision",
                        id=cut_id,
                        node_id=node_id,
                        target_node_id=node_id,
                    )
                if not by_id:
                    node = self.state.tableau.get_node(node_id)
                    if node is not None:
                        node.propogate_closed()
                    progress = True
                    break
                self.available_actions_by_goal[node_id] = by_id

            if progress:
                continue

            self.fringe_node_ids = new_fringe_ids
            self.state.evaluate_terminal(new_fringe_ids)
            return

    @property
    def action_space(self) -> Dict[int, Dict[str, Action]]:
        return self.available_actions_by_goal

    def resolve_action(self, action_ref: Any) -> Optional[Action]:
        if isinstance(action_ref, Action):
            actions = self.available_actions_by_goal.get(action_ref.node_id)
            if actions is None:
                return None
            return actions.get(action_ref.id)
        if isinstance(action_ref, dict):
            try:
                action = Action.from_dict(action_ref)
            except (KeyError, TypeError, ValueError):
                return None
            actions = self.available_actions_by_goal.get(action.node_id)
            if actions is None:
                return None
            return actions.get(action.id)
        return None

    @property
    def observation(self) -> Dict[str, Any]:
        nodes: Dict[int, Dict[str, Any]] = {}
        for node_id, node in self.state.tableau.all_nodes().items():
            parent_id = node.parent.node_id() if node.parent is not None else None
            child_ids = [child.node_id() for child in node.children]
            nodes[node_id] = {
                "parent_id": parent_id,
                "child_ids": child_ids,
                "literal": str(node.literal) if node.literal is not None else None,
            }

        actions_by_goal = {
            goal_id: {
                action_id: action.to_dict() for action_id, action in actions.items()
            }
            for goal_id, actions in self.available_actions_by_goal.items()
        }

        return {
            "root_node_id": self.state.tableau.node_id(),
            "fringe_node_ids": sorted(self.fringe_node_ids),
            "nodes": nodes,
            "available_actions_by_goal": actions_by_goal,
            "is_terminal": self.state.is_terminal,
            "info": self.state.info,
            "term_substitution": repr(self.state.term_substitution),
            "prefix_substitution": repr(self.state.prefix_substitution),
        }

    def step(self, action: Any) -> Tuple[Any, int, bool, Dict[str, str]]:
        if self.state.is_terminal:
            return (
                self.state,
                int(self.state.is_terminal),
                self.state.is_terminal,
                {"status": str(self.state.info)},
            )

        resolved_action = self.resolve_action(action)
        if resolved_action is None:
            return (
                self.state,
                0,
                self.state.is_terminal,
                {"status": "Invalid action"},
            )

        node = self.state.tableau.get_node(resolved_action.node_id)
        if node is None:
            return (
                self.state,
                0,
                self.state.is_terminal,
                {"status": "Invalid action"},
            )

        changed = False
        invalidate_all = False

        if resolved_action.action_type == "cut_decision":
            self.state.cut_decision(resolved_action.node_id)
            changed = True
            invalidate_all = True
        elif (
            resolved_action.action_type == "start"
            and resolved_action.clause_idx is not None
        ):
            changed = self.state.apply_start(
                resolved_action.node_id, resolved_action.clause_idx
            )
        elif (
            resolved_action.action_type == "extension"
            and resolved_action.clause_idx is not None
            and resolved_action.lit_idx is not None
        ):
            changed = self.state.apply_extension(
                resolved_action.node_id,
                resolved_action.clause_idx,
                resolved_action.lit_idx,
            )
        elif (
            resolved_action.action_type == "reduction"
            and resolved_action.path_node_id is not None
            and self.state.tableau.get_node(resolved_action.path_node_id) is not None
        ):
            changed = self.state.apply_reduction(
                resolved_action.node_id,
                resolved_action.path_node_id,
            )

        if not changed:
            return (
                self.state,
                0,
                self.state.is_terminal,
                {"status": "Invalid action"},
            )

        self._refresh_indexes_and_actions(invalidate_all=invalidate_all)
        return (
            self.state,
            int(self.state.is_terminal),
            self.state.is_terminal,
            {"status": str(self.state.info)},
        )

    def reset(self) -> Any:
        self.matrix = self._parse_matrix(self.path)
        self.state = State(self.matrix, self.settings)
        self.fringe_node_ids = set()
        self.available_actions_by_goal = {}
        self._refresh_indexes_and_actions(invalidate_all=True)
        return self.state
