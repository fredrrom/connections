from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from connections.logic.syntax import Literal
from connections.logic.tableau import Tableau


@dataclass
class Action:
    action_type: str
    id: str
    principle_node: Tableau
    clause_idx: Optional[int] = None
    lit_idx: Optional[int] = None
    clause_copy: Optional[Tuple[Literal, ...]] = None
    path_node: Optional[Tableau] = None
    sub_updates: List[Tuple[Any, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        if self.action_type in {"start", "extension"} and self.clause_copy is not None:
            head = (
                "root"
                if self.action_type == "start"
                else str(self.principle_node.literal)
            )
            return f"{self.id}: {head} -> [{', '.join(str(lit) for lit in self.clause_copy)}]"
        if self.action_type == "reduction" and self.path_node is not None:
            return (
                f"{self.id}: {self.principle_node.literal} -> {self.path_node.literal}"
            )
        return self.id
