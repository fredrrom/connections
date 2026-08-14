from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MatrixOptions": "connections.run.strategy",
    "PolicyOptions": "connections.run.strategy",
    "ProblemSpec": "connections.run.entry",
    "ProofFound": "connections.run.entry",
    "ProofFoundCallback": "connections.run.entry",
    "Result": "connections.run.result",
    "Rollout": "connections.run.rollout",
    "SZSStatus": "connections.run.szs",
    "ScheduledStrategy": "connections.run.strategy",
    "Strategy": "connections.run.strategy",
    "StrategyResult": "connections.run.result",
    "StrategySchedule": "connections.run.strategy",
    "WallClockExceeded": "connections.run.limits",
    "WeightedStrategy": "connections.run.strategy",
    "build_state": "connections.run.entry",
    "rollout": "connections.run.rollout",
    "run": "connections.run.entry",
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


# `rollout` names both a module in this package and the function it defines, and
# a submodule is bound as an attribute of its package by the import system --
# a lookup that wins before __getattr__ is ever consulted. Bind the function
# eagerly so the public name is the callable. (`run` avoids this by living in
# `entry`; see the note there.)
from connections.run.rollout import rollout as rollout  # noqa: E402
