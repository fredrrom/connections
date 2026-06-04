from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "LeancopSettingsCodec": "connections.pycop.settings_codec",
    "PycopStrategy": "connections.pycop.strategy",
    "PycopPolicy": "connections.pycop.policy",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
