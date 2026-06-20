from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from connections.syntax.matrix import Clause
from connections.constraints import ConstraintDelta

FactorizationMode: TypeAlias = Literal["equal", "unify"]


@dataclass(frozen=True, slots=True)
class Start:
    clause: Clause
    constraint_delta: ConstraintDelta = field(default_factory=ConstraintDelta)
    clause_idx: int | None = None
    instance_id: int | None = None


@dataclass(frozen=True, slots=True)
class Factorization:
    source_goal_id: int
    mode: FactorizationMode = "unify"
    constraint_delta: ConstraintDelta = field(default_factory=ConstraintDelta)


@dataclass(frozen=True, slots=True)
class Reduction:
    source_goal_id: int
    constraint_delta: ConstraintDelta = field(default_factory=ConstraintDelta)


@dataclass(frozen=True, slots=True)
class Extension:
    lit_idx: int
    clause: Clause
    constraint_delta: ConstraintDelta = field(default_factory=ConstraintDelta)
    clause_idx: int | None = None
    instance_id: int | None = None


Rule: TypeAlias = Start | Factorization | Reduction | Extension


__all__ = [
    "Extension",
    "Factorization",
    "FactorizationMode",
    "Reduction",
    "Rule",
    "Start",
]
