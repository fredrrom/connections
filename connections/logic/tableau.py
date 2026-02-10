from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(eq=False)
class Tableau:
    """A node in the proof tableau."""

    literal_idx: Optional[Tuple[int, int]] = None
    copy_num: int = 0
    path: Optional[Dict[Tuple[bool, str], List["Tableau"]]] = None
    parent: Optional["Tableau"] = None
    literal: Optional[Any] = None
    actions: Dict[str, Any] = field(default_factory=dict)
    children: List["Tableau"] = field(default_factory=list)
    closed_branches: int = 0

    def __post_init__(self) -> None:
        self.depth = self.parent.depth + 1 if self.parent is not None else -1

    def __str__(self) -> str:
        angle = "└── " if self.depth >= 0 else ""
        literal = getattr(self, "literal", self.literal_idx)
        ret = "    " * self.depth + angle + str(literal) + "\n"
        for child in self.children:
            ret += str(child)
        return ret

    def propogate_closed(self) -> None:
        self.closed_branches += 1
        if self.parent is not None and self.closed_branches >= len(self.children):
            self.parent.propogate_closed()
