"""The graph network: typed message passing plus action-edge scoring.

Plain torch, no graph framework: each relation is a pair of Linear
transforms (forward and reverse direction), messages are mean-aggregated
per relation and summed, node updates are gated through tanh with a
per-type self transform. Actions are scored from (kind embedding, source
goal embedding, target embedding). Two tiers: the matrix tier never
receives tableau messages, so its embeddings computed once per problem are
exact, not an approximation -- the task embedding, reused across every
decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import torch
from torch import nn

from imitation.representation.batch import GraphBatch, GraphTensors
from imitation.representation.schema import (
    ACTION_KINDS,
    ACTION_TARGET_TYPES,
    ARG_POSITION_BUCKETS,
    GraphInput,
    NODE_FEATURE_SIZES,
    NODE_TYPES,
    RELATIONS,
)

MATRIX_NODE_TYPES: tuple[str, ...] = ("symbol", "clause", "literal", "term", "var")
MATRIX_RELATIONS: tuple[str, ...] = (
    "contains",
    "atom",
    "arg_term",
    "arg_var",
    "sym",
    "lit_sym",
    "complement",
)
TABLEAU_RELATIONS: tuple[str, ...] = ("instance_of", "parent", "path")

_EdgeTensors = list[tuple[str, str, str, torch.Tensor, torch.Tensor | None]]


@dataclass(frozen=True, slots=True)
class GraphModelConfig:
    hidden_dim: int = 64
    message_rounds: int = 3
    num_hidden_layers: int = 2

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class GraphNetwork(nn.Module):
    def __init__(self, config: GraphModelConfig) -> None:
        super().__init__()
        self.config = config
        dim = config.hidden_dim
        self.feature_embeddings = nn.ModuleDict(
            {
                node_type: nn.ModuleList(
                    nn.Embedding(size, dim) for size in NODE_FEATURE_SIZES[node_type]
                )
                for node_type in NODE_TYPES
            }
        )
        self.position_embedding = nn.Embedding(ARG_POSITION_BUCKETS, dim)
        self.relation_fwd = nn.ModuleDict(
            {name: nn.Linear(dim, dim) for name, _, _, _ in RELATIONS}
        )
        self.relation_rev = nn.ModuleDict(
            {name: nn.Linear(dim, dim) for name, _, _, _ in RELATIONS}
        )
        self.self_transform = nn.ModuleDict(
            {node_type: nn.Linear(dim, dim) for node_type in NODE_TYPES}
        )
        # Residual + LayerNorm updates: the naked tanh(W h + messages)
        # recurrence diverges under per-example SGD once graphs are deep.
        self.update_norm = nn.ModuleDict(
            {node_type: nn.LayerNorm(dim) for node_type in NODE_TYPES}
        )
        self.kind_embedding = nn.Embedding(len(ACTION_KINDS), dim)
        self.missing_target = nn.Parameter(torch.zeros(dim))
        layers: list[nn.Module] = []
        input_dim = dim * 3
        for _ in range(config.num_hidden_layers):
            layers.append(nn.Linear(input_dim, dim))
            layers.append(nn.Tanh())
            input_dim = dim
        layers.append(nn.Linear(input_dim, 1))
        self.scorer = nn.Sequential(*layers)

    @property
    def _device(self) -> torch.device:
        return self.missing_target.device

    def _embed_features(
        self, node_type: str, rows: list[list[int]] | torch.Tensor
    ) -> torch.Tensor:
        dim = self.config.hidden_dim
        device = self._device
        if isinstance(rows, torch.Tensor):
            if rows.shape[0] == 0:
                return torch.zeros((0, dim), device=device)
            features = rows.to(device)
        elif not rows:
            return torch.zeros((0, dim), device=device)
        else:
            features = torch.tensor(rows, dtype=torch.long, device=device)
        embedded = torch.zeros((features.shape[0], dim), device=device)
        tables = cast(nn.ModuleList, self.feature_embeddings[node_type])
        for column, table in enumerate(tables):
            embedded = embedded + table(features[:, column])
        return torch.tanh(embedded)

    def _edge_tensors(
        self,
        graph: GraphInput | GraphTensors,
        names: tuple[str, ...],
    ) -> _EdgeTensors:
        by_name = {name: (src, dst, pos) for name, src, dst, pos in RELATIONS}
        tensors: _EdgeTensors = []
        for name in names:
            rows = graph.edges.get(name, [])
            if isinstance(rows, torch.Tensor):
                if rows.shape[0] == 0:
                    continue
            elif not rows:
                continue
            src_type, dst_type, has_position = by_name[name]
            tensor = (
                rows.to(self._device)
                if isinstance(rows, torch.Tensor)
                else torch.tensor(rows, dtype=torch.long, device=self._device)
            )
            position = tensor[:, 2] if has_position else None
            tensors.append((name, src_type, dst_type, tensor, position))
        return tensors

    def _message_rounds(
        self,
        h: dict[str, torch.Tensor],
        edge_tensors: _EdgeTensors,
        *,
        frozen: frozenset[str] = frozenset(),
    ) -> dict[str, torch.Tensor]:
        for _ in range(self.config.message_rounds):
            incoming = {
                node_type: torch.zeros_like(values)
                for node_type, values in h.items()
                if node_type not in frozen
            }
            for name, src_type, dst_type, tensor, position in edge_tensors:
                if dst_type not in frozen:
                    src_h = h[src_type][tensor[:, 0]]
                    if position is not None:
                        src_h = src_h + self.position_embedding(position)
                    _scatter_mean(
                        incoming[dst_type],
                        tensor[:, 1],
                        self.relation_fwd[name](src_h),
                    )
                if src_type not in frozen:
                    dst_h = h[dst_type][tensor[:, 1]]
                    if position is not None:
                        dst_h = dst_h + self.position_embedding(position)
                    _scatter_mean(
                        incoming[src_type],
                        tensor[:, 0],
                        self.relation_rev[name](dst_h),
                    )
            h = {
                node_type: (
                    values
                    if node_type in frozen
                    else self.update_norm[node_type](
                        values
                        + torch.tanh(
                            self.self_transform[node_type](values)
                            + incoming[node_type]
                        )
                    )
                )
                for node_type, values in h.items()
            }
        return h

    def encode_matrix(self, graph: GraphInput | GraphTensors) -> dict[str, torch.Tensor]:
        """Encode the static tier: reusable across every decision of a task."""

        h = {
            node_type: self._embed_features(node_type, graph.nodes.get(node_type, []))
            for node_type in MATRIX_NODE_TYPES
        }
        return self._message_rounds(h, self._edge_tensors(graph, MATRIX_RELATIONS))

    def encode(
        self,
        graph: GraphInput | GraphTensors,
        matrix_h: dict[str, torch.Tensor] | None = None,
    ) -> dict[str, torch.Tensor]:
        """Two-phase encode: frozen matrix tier, per-decision goal tier."""

        if matrix_h is None:
            matrix_h = self.encode_matrix(graph)
        h = dict(matrix_h)
        h["goal"] = self._embed_features("goal", graph.nodes.get("goal", []))
        return self._message_rounds(
            h,
            self._edge_tensors(graph, TABLEAU_RELATIONS),
            frozen=frozenset(MATRIX_NODE_TYPES),
        )

    def forward(
        self,
        graph: GraphInput | GraphTensors,
        matrix_h: dict[str, torch.Tensor] | None = None,
    ) -> torch.Tensor:
        h = self.encode(graph, matrix_h)
        actions = (
            graph.actions.to(self._device)
            if isinstance(graph.actions, torch.Tensor)
            else torch.tensor(graph.actions, dtype=torch.long, device=self._device)
        )
        kind = self.kind_embedding(actions[:, 0])
        source = h["goal"][actions[:, 1]]
        target = self.missing_target.expand(actions.shape[0], -1).clone()
        for type_index, type_name in enumerate(ACTION_TARGET_TYPES):
            if type_name == "none":
                continue
            mask = actions[:, 2] == type_index
            if mask.any():
                target[mask] = h[type_name][actions[mask, 3]]
        return self.scorer(torch.cat([kind, source, target], dim=1)).squeeze(1)

    def score_batch(self, batch: GraphBatch) -> torch.Tensor:
        """The collated batch is one merged disconnected graph: a single
        forward yields every example's action logits."""

        return self(batch.graph)


class GraphActionModel:
    """Greedy ActionModel wrapper: argmax over the shown candidates."""

    def __init__(self, *, model: GraphNetwork, device: str = "cpu") -> None:
        self.model = model.to(device)
        self.model.eval()
        self.device = torch.device(device)
        self._matrix_cache: dict[object, dict[str, torch.Tensor]] = {}

    def __call__(self, model_input: GraphInput) -> int:
        with torch.no_grad():
            logits = self.model(model_input, self._matrix_h(model_input))
        return int(torch.argmax(logits).item())

    def _matrix_h(self, graph: GraphInput) -> dict[str, torch.Tensor] | None:
        key = graph.metadata.get("matrix_key")
        if key is None:
            return None
        cached = self._matrix_cache.get(key)
        if cached is None:
            with torch.no_grad():
                cached = self.model.encode_matrix(graph)
            self._matrix_cache[key] = cached
            while len(self._matrix_cache) > 4:
                self._matrix_cache.pop(next(iter(self._matrix_cache)))
        return cached


def load_action_model(
    checkpoint_dir: str | Path, *, device: str = "cpu"
) -> GraphActionModel:
    checkpoint_path = Path(checkpoint_dir)
    if checkpoint_path.is_dir():
        checkpoint_path = checkpoint_path / "model.pt"
    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False
    )
    network = GraphNetwork(GraphModelConfig(**checkpoint["model_config"]))
    network.load_state_dict(checkpoint["model_state_dict"])
    return GraphActionModel(model=network, device=device)


class CheckpointActionModel:
    """A picklable ActionModel: the checkpoint path travels, weights load
    lazily on first call. What makes a fully configured learned agent one
    picklable value for a strategy's ``PolicyOptions.args``."""

    def __init__(self, checkpoint_dir: str | Path, *, device: str = "cpu") -> None:
        self.checkpoint_dir = str(checkpoint_dir)
        self.device = device
        self._loaded: GraphActionModel | None = None

    def __call__(self, model_input: GraphInput) -> int:
        if self._loaded is None:
            self._loaded = load_action_model(self.checkpoint_dir, device=self.device)
        return self._loaded(model_input)

    def __getstate__(self) -> dict[str, object]:
        return {"checkpoint_dir": self.checkpoint_dir, "device": self.device}

    def __setstate__(self, state: dict[str, object]) -> None:
        self.checkpoint_dir = str(state["checkpoint_dir"])
        self.device = str(state["device"])
        self._loaded = None


def _scatter_mean(
    output: torch.Tensor,
    index: torch.Tensor,
    values: torch.Tensor,
) -> None:
    counts = torch.zeros(output.shape[0], device=output.device)
    counts.index_add_(0, index, torch.ones(index.shape[0], device=output.device))
    summed = torch.zeros_like(output)
    summed.index_add_(0, index, values)
    output += summed / counts.clamp(min=1.0).unsqueeze(1)


__all__ = [
    "CheckpointActionModel",
    "GraphActionModel",
    "GraphModelConfig",
    "GraphNetwork",
    "load_action_model",
]
