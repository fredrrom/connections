from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MatrixOptions": "connections.interaction.strategy",
    "PolicyOptions": "connections.interaction.strategy",
    "Problem": "connections.interaction.run",
    "ProofFound": "connections.interaction.run",
    "ProofFoundCallback": "connections.interaction.run",
    "RESULT_SCHEMA": "connections.interaction.records",
    "Result": "connections.interaction.records",
    "action_record": "connections.interaction.records",
    "resolve_record": "connections.interaction.records",
    "Truncation": "connections.interaction.truncation",
    "Rollout": "connections.interaction.records",
    "SUCCESS": "connections.interaction.szs",
    "DECIDED": "connections.interaction.szs",
    "SZSStatus": "connections.interaction.szs",
    "ScheduledStrategy": "connections.interaction.strategy",
    "Strategy": "connections.interaction.strategy",
    "StrategyResult": "connections.interaction.records",
    "StrategySchedule": "connections.interaction.strategy",
    "WeightedStrategy": "connections.interaction.strategy",
    "build_state": "connections.interaction.run",
    "rollout": "connections.interaction.rollout",
    "run_schedule": "connections.interaction.run",
    "run_strategy": "connections.interaction.run",
    "to_szs_status": "connections.interaction.szs",
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
from connections.interaction.rollout import rollout as rollout  # noqa: E402
