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
    children: List["Tableau"] = field(default_factory=list)
    closed_branches: int = 0
    _root: Optional["Tableau"] = field(default=None, init=False, repr=False)
    _node_id: Optional[int] = field(default=None, init=False, repr=False)
    _next_node_id: int = field(default=0, init=False, repr=False)
    _node_by_id: Dict[int, "Tableau"] = field(
        default_factory=dict, init=False, repr=False
    )
    _id_by_node: Dict["Tableau", int] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.depth = self.parent.depth + 1 if self.parent is not None else -1
        if self.parent is None:
            self._root = self
            self._register_node(self)
        else:
            self._root = self.parent.root()
            self.root()._register_node(self)

    def root(self) -> "Tableau":
        assert self._root is not None
        return self._root

    def _register_node(self, node: "Tableau") -> int:
        if self is not self.root():
            return self.root()._register_node(node)
        node_id = self._next_node_id
        self._next_node_id += 1
        self._node_by_id[node_id] = node
        self._id_by_node[node] = node_id
        node._node_id = node_id
        return node_id

    def node_id(self) -> int:
        assert self._node_id is not None
        return self._node_id

    def get_node(self, node_id: int) -> Optional["Tableau"]:
        return self.root()._node_by_id.get(node_id)

    def get_node_id(self, node: "Tableau") -> int:
        return self.root()._id_by_node[node]

    def all_nodes(self) -> Dict[int, "Tableau"]:
        return dict(self.root()._node_by_id)

    def remove_subtree_from_index(self) -> None:
        for child in self.children:
            child.remove_subtree_from_index()
        root = self.root()
        node_id = self._node_id
        if node_id is not None and node_id in root._node_by_id:
            del root._node_by_id[node_id]
        if self in root._id_by_node:
            del root._id_by_node[self]

    def open_goals(self) -> List["Tableau"]:
        goals: List[Tableau] = []

        def visit(node: Tableau) -> None:
            if node.children:
                for child in node.children:
                    visit(child)
                return
            if not node.is_closed():
                goals.append(node)

        visit(self.root())
        return goals

    def open_goal_ids(self) -> List[int]:
        return [node.node_id() for node in self.open_goals()]

    def __str__(self) -> str:
        angle = "└── " if self.depth >= 0 else ""
        literal = getattr(self, "literal", self.literal_idx)
        ret = "    " * self.depth + angle + str(literal) + "\n"
        for child in self.children:
            ret += str(child)
        return ret

    def is_leaf(self) -> bool:
        return not self.children

    def is_closed(self) -> bool:
        if self.is_leaf():
            return self.closed_branches > 0
        return self.closed_branches >= len(self.children)

    def recompute_closed_branches(self) -> bool:
        if self.is_leaf():
            return self.is_closed()
        closed_children = 0
        for child in self.children:
            if child.recompute_closed_branches():
                closed_children += 1
        self.closed_branches = closed_children
        return self.is_closed()

    def propogate_closed(self) -> None:
        self.closed_branches += 1
        if self.parent is not None and self.is_closed():
            self.parent.propogate_closed()
