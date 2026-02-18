from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from connections.logic.substitution import SubstitutionUpdate
from connections.logic.syntax import Literal


@dataclass
class Action:
    action_type: str
    id: str
    node_id: int
    clause_idx: Optional[int] = None
    lit_idx: Optional[int] = None
    clause_copy: Optional[Tuple[Literal, ...]] = None
    path_node_id: Optional[int] = None
    target_node_id: Optional[int] = None
    sub_updates: List[SubstitutionUpdate] = field(default_factory=list)

    def __str__(self) -> str:
        if self.action_type == "cut_decision":
            return f"{self.id}: cut({self.target_node_id})"
        if self.action_type in {"start", "extension"} and self.clause_copy is not None:
            head = "root" if self.action_type == "start" else f"node:{self.node_id}"
            return f"{self.id}: {head} -> [{', '.join(str(lit) for lit in self.clause_copy)}]"
        if self.action_type == "reduction" and self.path_node_id is not None:
            return f"{self.id}: node:{self.node_id} -> node:{self.path_node_id}"
        return self.id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "id": self.id,
            "node_id": self.node_id,
            "clause_idx": self.clause_idx,
            "lit_idx": self.lit_idx,
            "path_node_id": self.path_node_id,
            "target_node_id": self.target_node_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(
            action_type=str(data["action_type"]),
            id=str(data["id"]),
            node_id=int(data["node_id"]),
            clause_idx=(
                int(data["clause_idx"]) if data.get("clause_idx") is not None else None
            ),
            lit_idx=(int(data["lit_idx"]) if data.get("lit_idx") is not None else None),
            path_node_id=(
                int(data["path_node_id"])
                if data.get("path_node_id") is not None
                else None
            ),
            target_node_id=(
                int(data["target_node_id"])
                if data.get("target_node_id") is not None
                else None
            ),
        )
