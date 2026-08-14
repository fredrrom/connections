from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MatrixOptions": "connections.run.strategy",
    "PolicyOptions": "connections.run.strategy",
    "ProblemSpec": "connections.run.prover",
    "Rollout": "connections.run.rollout",
    "ProofFound": "connections.run.prover",
    "ProofFoundCallback": "connections.run.prover",
    "Prover": "connections.run.prover",
    "ProverResult": "connections.run.prover",
    "SZSStatus": "connections.run.szs",
    "rollout": "connections.run.rollout",
    "ScheduledStrategy": "connections.run.strategy",
    "Strategy": "connections.run.strategy",
    "StrategyResult": "connections.run.prover",
    "StrategySchedule": "connections.run.strategy",
    "StrategyT": "connections.run.prover",
    "WallClockExceeded": "connections.run.prover",
    "WeightedStrategy": "connections.run.strategy",
    "to_szs_status": "connections.run.szs",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
