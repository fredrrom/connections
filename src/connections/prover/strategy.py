from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Generic, TypeVar

from connections.clausification import (
    ClausificationTranslationMode,
    StartClausesMode,
)
from connections.policy.dfs import DFSOptions, create_dfs_policy

StrategyT = TypeVar("StrategyT")


@dataclass(frozen=True, slots=True)
class MatrixOptions:
    translation: ClausificationTranslationMode = "default"
    reorder: int = 0
    start_clauses: StartClausesMode = "positive"


@dataclass(frozen=True, slots=True)
class DFSStrategy:
    matrix: MatrixOptions = field(default_factory=MatrixOptions)
    dfs: DFSOptions = field(default_factory=DFSOptions)

    def create_policy(self):
        return create_dfs_policy(self.dfs)


@dataclass(frozen=True, slots=True)
class WeightedStrategy(Generic[StrategyT]):
    strategy: StrategyT
    weight: int = 1


@dataclass(frozen=True, slots=True)
class ScheduledStrategy(Generic[StrategyT]):
    strategy: StrategyT
    step_limit: int | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class StrategySchedule(Generic[StrategyT]):
    entries: tuple[ScheduledStrategy[StrategyT], ...]

    @classmethod
    def from_weighted(
        cls,
        entries: tuple[WeightedStrategy[StrategyT], ...] | list[WeightedStrategy[StrategyT]],
        *,
        steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> StrategySchedule[StrategyT]:
        normalized = tuple(entries)
        if any(entry.weight < 0 for entry in normalized):
            raise ValueError("strategy weights must be non-negative")
        if not normalized:
            return cls(entries=())

        weights = [entry.weight for entry in normalized]
        step_limits = _allocate_int_budget(weights, steps, name="steps")
        time_limits = _allocate_float_budget(
            weights,
            timeout_seconds,
            name="timeout_seconds",
        )
        return cls(
            entries=tuple(
                ScheduledStrategy(
                    strategy=entry.strategy,
                    step_limit=None if step_limits is None else step_limits[index],
                    timeout_seconds=None if time_limits is None else time_limits[index],
                )
                for index, entry in enumerate(normalized)
            )
        )

    @classmethod
    def single(
        cls,
        strategy: StrategyT,
        *,
        steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> StrategySchedule[StrategyT]:
        if steps is not None and steps < 0:
            raise ValueError("steps must be non-negative")
        if timeout_seconds is not None and timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        return cls(
            entries=(
                ScheduledStrategy(
                    strategy=strategy,
                    step_limit=steps,
                    timeout_seconds=timeout_seconds,
                ),
            )
        )


def _allocate_int_budget(
    weights: list[int],
    total: int | None,
    *,
    name: str,
) -> tuple[int, ...] | None:
    if total is None:
        return None
    if total < 0:
        raise ValueError(f"{name} must be non-negative")
    if not weights:
        return ()

    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("strategy weights must sum to a positive value")

    raw = [total * weight / weight_sum for weight in weights]
    base = [math.floor(value) for value in raw]
    remainder = total - sum(base)
    order = sorted(
        range(len(weights)),
        key=lambda i: raw[i] - base[i],
        reverse=True,
    )
    for index in order[:remainder]:
        base[index] += 1
    return tuple(base)


def _allocate_float_budget(
    weights: list[int],
    total: float | None,
    *,
    name: str,
) -> tuple[float, ...] | None:
    if total is None:
        return None
    if total < 0:
        raise ValueError(f"{name} must be non-negative")
    if not weights:
        return ()

    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("strategy weights must sum to a positive value")

    allocated = [total * weight / weight_sum for weight in weights]
    allocated[-1] = max(0.0, total - sum(allocated[:-1]))
    return tuple(allocated)

__all__ = [
    "DFSStrategy",
    "MatrixOptions",
    "ScheduledStrategy",
    "StrategySchedule",
    "WeightedStrategy",
]
