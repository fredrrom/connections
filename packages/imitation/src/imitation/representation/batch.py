"""Batch collation: many decisions as one merged disconnected graph.

Node tables concatenate per type with offsets, edge and action indices shift
accordingly. Because message flow is matrix -> goal only and parent/path
edges never cross examples, disconnected components compute independently:
batched logits equal per-example logits. Examples that share a matrix tier
(same ``matrix_key``) share one copy of it in the merged graph, so the
static tier's cost is paid once per problem per batch.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import torch

from imitation.records import Example
from imitation.representation.schema import (
    NODE_FEATURE_SIZES,
    RELATIONS,
    GraphInput,
)

_MATRIX_NODE_TYPES = ("symbol", "clause", "literal", "term", "var")
_NODE_WIDTH = {t: len(sizes) for t, sizes in NODE_FEATURE_SIZES.items()}
_EDGE_WIDTH = {name: (3 if has_pos else 2) for name, _, _, has_pos in RELATIONS}
_MATRIX_EDGES = {
    name: (src, dst)
    for name, src, dst, _ in RELATIONS
    if src != "goal" and dst != "goal"
}
_TABLEAU_EDGES = {
    name: (src, dst)
    for name, src, dst, _ in RELATIONS
    if src == "goal" or dst == "goal"
}


@dataclass(frozen=True, slots=True)
class GraphTensors:
    """A graph with every table already a LongTensor, ready for the model."""

    nodes: dict[str, torch.Tensor]
    edges: dict[str, torch.Tensor]
    actions: torch.Tensor
    metadata: dict[str, Any] = field(default_factory=dict)

    def to(self, device: torch.device | str) -> GraphTensors:
        return GraphTensors(
            nodes={k: v.to(device) for k, v in self.nodes.items()},
            edges={k: v.to(device) for k, v in self.edges.items()},
            actions=self.actions.to(device),
            metadata=self.metadata,
        )


@dataclass(frozen=True, slots=True)
class TensorizedExample:
    """One example's tables converted to LongTensors, once, at load time."""

    nodes: dict[str, torch.Tensor]
    edges: dict[str, torch.Tensor]
    actions: torch.Tensor
    chosen: int
    matrix_key: object


@dataclass(frozen=True, slots=True)
class GraphBatch:
    """One merged graph plus per-example segmentation of its action rows."""

    graph: GraphTensors
    action_counts: torch.Tensor
    chosen_indices: torch.Tensor

    def to(self, device: torch.device | str) -> GraphBatch:
        return GraphBatch(
            graph=self.graph.to(device),
            action_counts=self.action_counts.to(device),
            chosen_indices=self.chosen_indices.to(device),
        )


def tensorize(graph: GraphInput, chosen_index: int) -> TensorizedExample:
    nodes = {}
    for node_type in (*_MATRIX_NODE_TYPES, "goal"):
        rows = graph.nodes.get(node_type, [])
        nodes[node_type] = torch.tensor(rows, dtype=torch.long).reshape(
            -1, _NODE_WIDTH[node_type]
        )
    edges = {}
    for name in (*_MATRIX_EDGES, *_TABLEAU_EDGES):
        rows = graph.edges.get(name, [])
        edges[name] = torch.tensor(rows, dtype=torch.long).reshape(
            -1, _EDGE_WIDTH[name]
        )
    actions = torch.tensor(graph.actions, dtype=torch.long).reshape(-1, 4)
    return TensorizedExample(
        nodes=nodes,
        edges=edges,
        actions=actions,
        chosen=chosen_index,
        matrix_key=graph.metadata.get("matrix_key"),
    )


def collate(examples: Sequence[TensorizedExample]) -> GraphBatch:
    """Merge examples: matrix blocks shared per key, first occurrence wins."""

    if not examples:
        raise ValueError("cannot collate an empty batch")

    node_parts: dict[str, list[torch.Tensor]] = {
        t: [] for t in (*_MATRIX_NODE_TYPES, "goal")
    }
    node_counts: dict[str, int] = {t: 0 for t in node_parts}
    edge_parts: dict[str, list[torch.Tensor]] = {
        name: [] for name in (*_MATRIX_EDGES, *_TABLEAU_EDGES)
    }
    action_parts: list[torch.Tensor] = []
    action_counts: list[int] = []
    chosen: list[int] = []
    matrix_offsets: dict[object, dict[str, int]] = {}

    def shift(rows: torch.Tensor, src_off: int, dst_off: int) -> torch.Tensor:
        if rows.numel() == 0:
            return rows
        shifted = rows.clone()
        shifted[:, 0] += src_off
        shifted[:, 1] += dst_off
        return shifted

    for index, example in enumerate(examples):
        key = example.matrix_key if example.matrix_key is not None else (
            "unshared",
            index,
        )
        offsets = matrix_offsets.get(key)
        if offsets is None:
            offsets = {t: node_counts[t] for t in _MATRIX_NODE_TYPES}
            for node_type in _MATRIX_NODE_TYPES:
                block = example.nodes[node_type]
                node_parts[node_type].append(block)
                node_counts[node_type] += block.shape[0]
            for name, (src_type, dst_type) in _MATRIX_EDGES.items():
                edge_parts[name].append(
                    shift(example.edges[name], offsets[src_type], offsets[dst_type])
                )
            matrix_offsets[key] = offsets

        goal_offset = node_counts["goal"]
        node_parts["goal"].append(example.nodes["goal"])
        node_counts["goal"] += example.nodes["goal"].shape[0]

        for name, (src_type, dst_type) in _TABLEAU_EDGES.items():
            src_off = goal_offset if src_type == "goal" else offsets[src_type]
            dst_off = goal_offset if dst_type == "goal" else offsets[dst_type]
            edge_parts[name].append(shift(example.edges[name], src_off, dst_off))

        actions = example.actions.clone()
        if actions.numel():
            actions[:, 1] += goal_offset
            # Target shift depends on target type: none -> 0, clause and
            # literal -> matrix offsets, goal -> this example's goal block.
            target_offsets = torch.tensor(
                [0, offsets["clause"], offsets["literal"], goal_offset],
                dtype=torch.long,
            )
            actions[:, 3] += target_offsets[actions[:, 2]]
        action_parts.append(actions)
        action_counts.append(actions.shape[0])
        chosen.append(example.chosen)

    merged = GraphTensors(
        nodes={t: torch.cat(parts) for t, parts in node_parts.items()},
        edges={n: torch.cat(parts) for n, parts in edge_parts.items()},
        actions=torch.cat(action_parts),
        metadata={"batch_size": len(examples)},
    )
    return GraphBatch(
        graph=merged,
        action_counts=torch.tensor(action_counts, dtype=torch.long),
        chosen_indices=torch.tensor(chosen, dtype=torch.long),
    )


class GraphDataset:
    """Tensorized examples on one surface.

    Mixing surfaces would train on label spaces the deployed chooser never
    shows, so construction refuses a mixed dataset outright.
    """

    def __init__(self, examples: Sequence[Example]) -> None:
        keys = {example.surface_key for example in examples}
        if len(keys) > 1:
            raise ValueError(
                f"examples mix action surfaces: {sorted(keys)!r}"
            )
        self.surface_key = next(iter(keys)) if keys else None
        self.examples = tuple(examples)
        self.items = tuple(
            tensorize(example.model_input, example.chosen_index)
            for example in examples
        )

    def __len__(self) -> int:
        return len(self.items)


__all__ = [
    "GraphBatch",
    "GraphDataset",
    "GraphTensors",
    "TensorizedExample",
    "collate",
    "tensorize",
]
