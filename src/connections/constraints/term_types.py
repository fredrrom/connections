from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias

from connections.core.formula import Atom, Term, Variable
from connections.core.matrix import Literal


@dataclass(frozen=True, slots=True, eq=False)
class TableauVariable:
    instance_id: int
    source: Variable
    _key: tuple[object, ...] = field(init=False, compare=False, repr=False)
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        key = (
            self.instance_id,
            self.source.symbol,
            self.source.vid,
            self.source.prefix,
        )
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_hash", hash(key))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is TableauVariable
            and self._hash == other._hash
            and self._key == other._key
        )

    @property
    def symbol(self) -> str:
        return self.source.symbol

    @property
    def prefix(self):
        return self.source.prefix

    @property
    def is_ground(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.source.symbol


TableauVariableKey: TypeAlias = tuple[int, Variable]
TermSubstitutionVariable: TypeAlias = Variable | TableauVariableKey
TermSubstitutionTerm: TypeAlias = Term | TableauVariable
TermSubstitutionInputTerm: TypeAlias = TermSubstitutionTerm | TableauVariableKey
TermSubstitutionAtom: TypeAlias = Atom
TermSubstitutionLiteral: TypeAlias = Literal
TermReference: TypeAlias = tuple[Any, int | None]
TermBinding: TypeAlias = tuple[TermSubstitutionVariable, TermReference]
TermRef: TypeAlias = tuple[Any, int | None]
ScopedTerm: TypeAlias = tuple[int, TermSubstitutionInputTerm | TermSubstitutionAtom]
ScopedVariable: TypeAlias = tuple[int, TermSubstitutionVariable]


@dataclass(slots=True)
class ResolveCacheEntry:
    revision: int
    resolved: Any


@dataclass(slots=True)
class LiteralCacheEntry:
    revision: int
    resolved: TermSubstitutionLiteral


__all__ = [
    "LiteralCacheEntry",
    "ResolveCacheEntry",
    "ScopedTerm",
    "ScopedVariable",
    "TableauVariable",
    "TableauVariableKey",
    "TermBinding",
    "TermRef",
    "TermReference",
    "TermSubstitutionAtom",
    "TermSubstitutionInputTerm",
    "TermSubstitutionLiteral",
    "TermSubstitutionTerm",
    "TermSubstitutionVariable",
]
