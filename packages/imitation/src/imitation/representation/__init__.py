"""The state representation: graph schema, matrix tier, preprocessing.

``schema``, ``matrix`` and ``preprocess`` are torch-free; only ``batch``
pays the torch import, at training time.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ACTION_KINDS": "imitation.representation.schema",
    "GraphInput": "imitation.representation.schema",
    "NODE_FEATURE_SIZES": "imitation.representation.schema",
    "NODE_TYPES": "imitation.representation.schema",
    "RELATIONS": "imitation.representation.schema",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
