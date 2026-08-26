"""The trainer: fit the network to the critic's feedback, checkpoint it.

No DataLoader machinery: a seeded permutation into collated chunks is the
whole batching story, which keeps runs deterministic per seed. The
checkpoint is ``model.pt`` plus ``metrics.json``, written last as the
commit marker -- its presence implies a complete checkpoint -- and it
carries the dataset's ``surface_key``, so what a model was trained to
choose over is never ambient knowledge.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import torch

from collections.abc import Sequence

from imitation.learning.objective import segmented_accuracy, segmented_cross_entropy
from imitation.model import (
    CheckpointActionModel,
    GraphModelConfig,
    GraphNetwork,
)
from imitation.records import Example, choicepoint_key, dedupe
from imitation.representation.batch import GraphDataset, collate


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    epochs: int = 2
    batch_size: int = 8
    learning_rate: float = 1e-4
    lr_schedule: str = "none"
    lr_min: float = 1e-4
    target_train_accuracy: float | None = None
    patience: int | None = None
    min_delta: float = 0.0
    seed: int = 0
    device: str = "auto"


@dataclass(frozen=True, slots=True)
class TrainingReport:
    examples: int
    epochs: int
    stopped_reason: str
    best_epoch: int
    best_train_accuracy: float
    best_train_loss: float
    device: str
    wall_elapsed_seconds: float
    surface_key: str | None
    history: tuple[dict[str, float], ...] = field(default=())


logger = logging.getLogger(__name__)

_PROGRESS_SECONDS = 5.0


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def train(
    dataset: GraphDataset,
    *,
    model: GraphNetwork,
    config: TrainingConfig | None = None,
    output_dir: str | Path,
) -> TrainingReport:
    started_at = time.perf_counter()
    config = config or TrainingConfig()
    if len(dataset) == 0:
        raise ValueError("cannot train on an empty dataset")
    if config.patience is not None and config.patience < 1:
        raise ValueError("patience must be positive or None")
    if config.min_delta < 0:
        raise ValueError("min_delta must be non-negative")

    device = torch.device(resolve_device(config.device))
    torch.manual_seed(config.seed)
    generator = torch.Generator().manual_seed(config.seed)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    if config.lr_schedule == "cosine":
        scheduler: torch.optim.lr_scheduler.LRScheduler | None = (
            torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=config.epochs, eta_min=config.lr_min
            )
        )
    elif config.lr_schedule == "none":
        scheduler = None
    else:
        raise ValueError(f"unknown lr_schedule: {config.lr_schedule!r}")

    logger.info(
        "training: %d examples, %d epochs max, device %s",
        len(dataset),
        config.epochs,
        device,
    )
    last_report = time.monotonic()
    history: list[dict[str, float]] = []
    stopped_reason = "max_epochs"
    best_train_loss = float("inf")
    best_train_accuracy = -1.0
    best_epoch = 0
    convergence_best = None
    non_improving = 0

    for epoch in range(config.epochs):
        order = torch.randperm(len(dataset), generator=generator).tolist()
        _run_epoch(model, dataset, order, config, optimizer=optimizer, device=device)
        if scheduler is not None:
            scheduler.step()
        # The reported epoch metrics come from a separate frozen pass, so
        # they describe one set of weights, not a moving average.
        evaluated = _run_epoch(
            model,
            dataset,
            list(range(len(dataset))),
            config,
            optimizer=None,
            device=device,
        )
        history.append({"epoch": float(epoch + 1), **evaluated})
        logger.debug(
            "epoch %d: loss %.4f, accuracy %.3f",
            epoch + 1,
            evaluated["loss"],
            evaluated["accuracy"],
        )
        now = time.monotonic()
        if now - last_report >= _PROGRESS_SECONDS:
            logger.info(
                "epoch %d/%d: loss %.4f, accuracy %.3f",
                epoch + 1,
                config.epochs,
                evaluated["loss"],
                evaluated["accuracy"],
            )
            last_report = now

        tracks_accuracy = config.target_train_accuracy is not None
        if evaluated["loss"] < best_train_loss:
            best_train_loss = evaluated["loss"]
            if not tracks_accuracy:
                best_epoch = epoch + 1
        if evaluated["accuracy"] > best_train_accuracy:
            best_train_accuracy = evaluated["accuracy"]
            if tracks_accuracy:
                best_epoch = epoch + 1

        if (
            config.target_train_accuracy is not None
            and evaluated["accuracy"] >= config.target_train_accuracy
        ):
            stopped_reason = "target_train_accuracy"
            break
        if config.patience is not None:
            tracked = evaluated["accuracy"] if tracks_accuracy else -evaluated["loss"]
            if convergence_best is None or tracked > convergence_best + config.min_delta:
                convergence_best = tracked
                non_improving = 0
            else:
                non_improving += 1
            if non_improving >= config.patience:
                stopped_reason = (
                    "train_accuracy_convergence"
                    if tracks_accuracy
                    else "train_loss_convergence"
                )
                break

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_config": model.config.to_dict(),
            "training_config": asdict(config),
            "surface_key": dataset.surface_key,
        },
        output / "model.pt",
    )
    report = TrainingReport(
        examples=len(dataset),
        epochs=len(history),
        stopped_reason=stopped_reason,
        best_epoch=best_epoch,
        best_train_accuracy=best_train_accuracy,
        best_train_loss=best_train_loss,
        device=str(device),
        wall_elapsed_seconds=time.perf_counter() - started_at,
        surface_key=dataset.surface_key,
        history=tuple(history),
    )
    # metrics.json is the checkpoint commit marker: written atomically and
    # last, so its presence implies a complete checkpoint.
    metrics_tmp = output / ".metrics.json.tmp"
    metrics_tmp.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True), encoding="utf-8"
    )
    metrics_tmp.replace(output / "metrics.json")
    logger.info(
        "trained %d epochs in %.1fs (%s): accuracy %.3f, checkpoint %s",
        report.epochs,
        report.wall_elapsed_seconds,
        report.stopped_reason,
        report.best_train_accuracy,
        output,
    )
    return report


def _run_epoch(
    model: GraphNetwork,
    dataset: GraphDataset,
    order: list[int],
    config: TrainingConfig,
    *,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_correct = 0
    total_examples = 0

    with torch.set_grad_enabled(training):
        for start in range(0, len(order), config.batch_size):
            indices = order[start : start + config.batch_size]
            batch = collate([dataset.items[i] for i in indices]).to(device)
            logits = model.score_batch(batch)
            loss = segmented_cross_entropy(
                logits, batch.action_counts, batch.chosen_indices
            )
            if optimizer is not None:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            count = int(batch.chosen_indices.numel())
            total_loss += float(loss.detach()) * count
            total_correct += segmented_accuracy(
                logits.detach(), batch.action_counts, batch.chosen_indices
            )
            total_examples += count

    if total_examples == 0:
        return {"loss": 0.0, "accuracy": 0.0}
    return {
        "loss": total_loss / total_examples,
        "accuracy": total_correct / total_examples,
    }


@dataclass(slots=True)
class SupervisedLearner:
    """The learning element: fit the network to the feedback, from scratch.

    The update is the whole DAgger barrier: deduplicate the accumulated
    demonstrations, order them canonically so training does not depend on
    collection order, fit a fresh network, checkpoint it, and hand back a
    picklable model for the next wave's actors.
    """

    model_config: GraphModelConfig = field(default_factory=GraphModelConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    device: str = "cpu"

    def improve(
        self, feedback: Sequence[Example], *, output_dir: Path
    ) -> CheckpointActionModel:
        dataset = GraphDataset(sorted(dedupe(feedback), key=choicepoint_key))
        train(
            dataset,
            model=GraphNetwork(self.model_config),
            config=self.training,
            output_dir=output_dir,
        )
        return CheckpointActionModel(output_dir, device=self.device)


__all__ = [
    "SupervisedLearner",
    "TrainingConfig",
    "TrainingReport",
    "resolve_device",
    "train",
]
