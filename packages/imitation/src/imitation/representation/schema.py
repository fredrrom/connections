"""The graph schema: what a decision looks like to the model.

One decision is a typed graph over two tiers -- the matrix tier (symbols,
clauses, literals, terms, variables), which depends only on the task, and
the goal tier (goals), which depends on the derivation -- plus one row per
candidate action. The layout here is the single source of truth shared by
the preprocessor (writer) and the model (reader). Everything is plain ints
and lists, so an input JSON-round-trips through the example records
unchanged; nothing in this module imports torch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

NODE_TYPES: tuple[str, ...] = (
    "symbol",
    "clause",
    "literal",
    "term",
    "var",
    "goal",
)

# Per node type: the cardinality of each categorical feature, in order.
NODE_FEATURE_SIZES: dict[str, tuple[int, ...]] = {
    # kind (predicate/function/constant), arity bucket
    "symbol": (3, 5),
    # size bucket, role (axiom/conjecture/other), is_ground, is_start
    "clause": (5, 3, 2, 2),
    # polarity
    "literal": (2,),
    # is_ground
    "term": (2,),
    # single dummy category: identity comes from edges alone
    "var": (1,),
    # is_open, depth bucket
    "goal": (2, 8),
}

# (name, source node type, destination node type, has positional feature)
RELATIONS: tuple[tuple[str, str, str, bool], ...] = (
    ("contains", "clause", "literal", False),
    ("atom", "literal", "term", False),
    ("arg_term", "term", "term", True),
    ("arg_var", "term", "var", True),
    ("sym", "term", "symbol", False),
    ("lit_sym", "literal", "symbol", False),
    ("complement", "literal", "literal", False),
    ("instance_of", "goal", "literal", False),
    ("parent", "goal", "goal", False),
    ("path", "goal", "goal", False),
)

ARG_POSITION_BUCKETS = 6

ACTION_KINDS: tuple[str, ...] = (
    "start",
    "extension",
    "reduction",
    "factorization",
    "backtrack",
)

# Target node type per action row; "none" means the kind embedding and the
# source goal carry the whole description (backtrack).
ACTION_TARGET_TYPES: tuple[str, ...] = ("none", "clause", "literal", "goal")


@dataclass(frozen=True, slots=True)
class GraphInput:
    """One decision: typed nodes, typed edges, candidate actions as rows.

    The action rows are the label space: row i describes the i-th candidate
    the chooser was shown, in order, so an example's ``chosen_index``
    indexes both. ``metadata`` is provenance (matrix key, counts), never
    identity.

    nodes: node type -> [[feature categories] per node]
    edges: relation name -> [[src, dst] or [src, dst, position]]
    actions: [[kind, source goal index, target type, target index]]
    """

    nodes: dict[str, list[list[int]]]
    edges: dict[str, list[list[int]]]
    actions: list[list[int]]
    preprocessor: str = "graph"
    version: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GraphInput:
        return cls(
            nodes={
                key: [list(row) for row in val]
                for key, val in payload["nodes"].items()
            },
            edges={
                key: [list(row) for row in val]
                for key, val in payload["edges"].items()
            },
            actions=[list(row) for row in payload["actions"]],
            preprocessor=payload.get("preprocessor", "graph"),
            version=payload.get("version", "1"),
            metadata=dict(payload.get("metadata", {})),
        )


def arg_position_bucket(position: int) -> int:
    return min(position, ARG_POSITION_BUCKETS - 1)


__all__ = [
    "ACTION_KINDS",
    "ACTION_TARGET_TYPES",
    "ARG_POSITION_BUCKETS",
    "GraphInput",
    "NODE_FEATURE_SIZES",
    "NODE_TYPES",
    "RELATIONS",
    "arg_position_bucket",
]
