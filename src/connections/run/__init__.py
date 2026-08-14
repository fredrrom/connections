from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MatrixOptions": "connections.run.strategy",
    "PolicyOptions": "connections.run.strategy",
    "ProblemSpec": "connections.run.run",
    "ProofFound": "connections.run.run",
    "ProofFoundCallback": "connections.run.run",
    "Result": "connections.run.result",
    "Rollout": "connections.run.rollout",
    "SZSStatus": "connections.run.szs",
    "ScheduledStrategy": "connections.run.strategy",
    "Strategy": "connections.run.strategy",
    "StrategyResult": "connections.run.result",
    "StrategySchedule": "connections.run.strategy",
    "WallClockExceeded": "connections.run.limits",
    "WeightedStrategy": "connections.run.strategy",
    "build_state": "connections.run.run",
    "rollout": "connections.run.rollout",
    "run": "connections.run.run",
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
