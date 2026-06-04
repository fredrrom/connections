from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "Action": "connections.prover.actions",
    "ActionChoice": "connections.prover.actions",
    "AnyApplyAction": "connections.prover.actions",
    "ApplyAction": "connections.prover.actions",
    "ApplyActions": "connections.prover.actions",
    "Domain": "connections.core.logic",
    "Dynamics": "connections.prover.dynamics",
    "DFSStrategy": "connections.prover.strategy",
    "ExtensionAction": "connections.prover.actions",
    "FactorizationAction": "connections.prover.actions",
    "Logic": "connections.core.logic",
    "MatrixOptions": "connections.prover.strategy",
    "Problem": "connections.prover.prover",
    "Prover": "connections.prover.prover",
    "ProverHook": "connections.prover.prover",
    "ProverResult": "connections.prover.prover",
    "State": "connections.prover.state",
    "StrategyResult": "connections.prover.prover",
    "ScheduledStrategy": "connections.prover.strategy",
    "ReductionAction": "connections.prover.actions",
    "StartAction": "connections.prover.actions",
    "StrategySchedule": "connections.prover.strategy",
    "UndoAction": "connections.prover.actions",
    "WeightedStrategy": "connections.prover.strategy",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
