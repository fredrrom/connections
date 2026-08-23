from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "Action": "connections.environment.actions",
    "AnyApplyAction": "connections.environment.actions",
    "ApplyAction": "connections.environment.actions",
    "ApplyActions": "connections.environment.actions",
    "Dynamics": "connections.environment.dynamics",
    "Extension": "connections.environment.rules",
    "ExtensionAction": "connections.environment.actions",
    "Factorization": "connections.environment.rules",
    "FactorizationAction": "connections.environment.actions",
    "FactorizationMode": "connections.environment.rules",
    "Reduction": "connections.environment.rules",
    "ReductionAction": "connections.environment.actions",
    "Rule": "connections.environment.rules",
    "RuleApplication": "connections.environment.tableau",
    "RuleCache": "connections.environment.tableau",
    "RuleT": "connections.environment.dynamics",
    "Start": "connections.environment.rules",
    "StartAction": "connections.environment.actions",
    "State": "connections.environment.state",
    "Tableau": "connections.environment.tableau",
    "TableauNode": "connections.environment.tableau",
    "UndoAction": "connections.environment.actions",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
