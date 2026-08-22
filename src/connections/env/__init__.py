from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "Action": "connections.env.actions",
    "AnyApplyAction": "connections.env.actions",
    "ApplyAction": "connections.env.actions",
    "ApplyActions": "connections.env.actions",
    "Dynamics": "connections.env.dynamics",
    "Extension": "connections.env.rules",
    "ExtensionAction": "connections.env.actions",
    "Factorization": "connections.env.rules",
    "FactorizationAction": "connections.env.actions",
    "FactorizationMode": "connections.env.rules",
    "Reduction": "connections.env.rules",
    "ReductionAction": "connections.env.actions",
    "Rule": "connections.env.rules",
    "RuleApplication": "connections.env.tableau",
    "RuleCache": "connections.env.tableau",
    "RuleT": "connections.env.dynamics",
    "Start": "connections.env.rules",
    "StartAction": "connections.env.actions",
    "State": "connections.env.state",
    "Tableau": "connections.env.tableau",
    "TableauNode": "connections.env.tableau",
    "UndoAction": "connections.env.actions",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
