from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from connections.syntax.logic import Logic
from provers.pycop.settings_codec import LeancopSettingsCodec
from connections.prover.strategy import Strategy, WeightedStrategy


def _entry(tokens: list[str], weight: int) -> WeightedStrategy[Strategy]:
    return WeightedStrategy(strategy=LeancopSettingsCodec.from_tokens(tokens), weight=weight)


_SCHEDULE_DIR = Path(__file__).with_name("schedules")
_BUILTIN_SCHEDULE_PATHS = {
    "classical": _SCHEDULE_DIR / "classical.json",
    "intuitionistic": _SCHEDULE_DIR / "intuitionistic.json",
    "modal": _SCHEDULE_DIR / "modal.json",
}


def load_schedule_entries(path_or_name: str | Path) -> list[WeightedStrategy[Strategy]]:
    if isinstance(path_or_name, str) and path_or_name in _BUILTIN_SCHEDULE_PATHS:
        return _load_schedule_file(_BUILTIN_SCHEDULE_PATHS[path_or_name])
    return _load_schedule_file(Path(path_or_name))


def _load_schedule_file(path: Path) -> list[WeightedStrategy[Strategy]]:
    return _entries_from_json(json.loads(path.read_text(encoding="utf-8")))


def _entries_from_json(data: object) -> list[WeightedStrategy[Strategy]]:
    if isinstance(data, Mapping):
        root = cast(Mapping[str, object], data)
        data = root.get("entries")
    if not isinstance(data, list):
        raise ValueError("schedule file must contain a list or an object with entries")

    entries: list[WeightedStrategy[Strategy]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"schedule entry {index} must be an object")
        entry = cast(Mapping[str, object], item)
        tokens = entry.get("settings")
        if tokens is None:
            tokens = entry.get("tokens", [])
        if not isinstance(tokens, list) or not all(
            isinstance(token, str) for token in tokens
        ):
            raise ValueError(f"schedule entry {index} settings must be a string list")
        token_list = cast(list[str], tokens)
        weight = entry.get("weight", 1)
        if not isinstance(weight, int):
            raise ValueError(f"schedule entry {index} weight must be an integer")
        entries.append(_entry(token_list, weight))
    return entries


def _load_builtin_schedule(name: str) -> list[WeightedStrategy[Strategy]]:
    return _load_schedule_file(_BUILTIN_SCHEDULE_PATHS[name])


_CLASSICAL_SCHEDULE = _load_builtin_schedule("classical")
_INTUITIONISTIC_SCHEDULE = _load_builtin_schedule("intuitionistic")
_MODAL_SCHEDULE = _load_builtin_schedule("modal")

SCHEDULE_BY_LOGIC: dict[Logic, list[WeightedStrategy[Strategy]]] = {
    "classical": _CLASSICAL_SCHEDULE,
    "intuitionistic": _INTUITIONISTIC_SCHEDULE,
    "D": _MODAL_SCHEDULE,
    "T": _MODAL_SCHEDULE,
    "S4": _MODAL_SCHEDULE,
    "S5": _MODAL_SCHEDULE,
}


__all__ = [
    "load_schedule_entries",
    "SCHEDULE_BY_LOGIC",
    "WeightedStrategy",
]
