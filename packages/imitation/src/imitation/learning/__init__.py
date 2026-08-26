"""The learning element: objective and trainer."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "TrainingConfig": "imitation.learning.trainer",
    "TrainingReport": "imitation.learning.trainer",
    "segmented_accuracy": "imitation.learning.objective",
    "segmented_cross_entropy": "imitation.learning.objective",
    "train": "imitation.learning.trainer",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
