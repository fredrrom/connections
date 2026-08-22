from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "Action": "connections.calculus.actions",
    "AnyApplyAction": "connections.calculus.actions",
    "ApplyAction": "connections.calculus.actions",
    "ApplyActions": "connections.calculus.actions",
    "Dynamics": "connections.calculus.dynamics",
    "Extension": "connections.calculus.rules",
    "ExtensionAction": "connections.calculus.actions",
    "Factorization": "connections.calculus.rules",
    "FactorizationAction": "connections.calculus.actions",
    "FactorizationMode": "connections.calculus.rules",
    "Reduction": "connections.calculus.rules",
    "ReductionAction": "connections.calculus.actions",
    "Rule": "connections.calculus.rules",
    "RuleApplication": "connections.calculus.tableau",
    "RuleCache": "connections.calculus.tableau",
    "RuleT": "connections.calculus.dynamics",
    "Start": "connections.calculus.rules",
    "StartAction": "connections.calculus.actions",
    "State": "connections.calculus.state",
    "Tableau": "connections.calculus.tableau",
    "TableauNode": "connections.calculus.tableau",
    "UndoAction": "connections.calculus.actions",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
