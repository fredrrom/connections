from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "Action": "connections.prover.actions",
    "AnyApplyAction": "connections.prover.actions",
    "ApplyAction": "connections.prover.actions",
    "ApplyActions": "connections.prover.actions",
    "Domain": "connections.syntax.logic",
    "Dynamics": "connections.prover.dynamics",
    "ExtensionAction": "connections.prover.actions",
    "FactorizationAction": "connections.prover.actions",
    "Logic": "connections.syntax.logic",
    "MatrixOptions": "connections.prover.strategy",
    "Problem": "connections.prover.prover",
    "ProofFound": "connections.prover.prover",
    "ProofFoundCallback": "connections.prover.prover",
    "PolicyOptions": "connections.prover.strategy",
    "ProblemSpec": "connections.prover.prover",
    "Prover": "connections.prover.prover",
    "ProverOutcome": "connections.prover.status",
    "ProverResult": "connections.prover.prover",
    "State": "connections.prover.state",
    "StrategyResult": "connections.prover.prover",
    "SZSStatus": "connections.prover.status",
    "ScheduledStrategy": "connections.prover.strategy",
    "ReductionAction": "connections.prover.actions",
    "StartAction": "connections.prover.actions",
    "Strategy": "connections.prover.strategy",
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
