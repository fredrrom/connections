from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, TypeAlias, Union


@dataclass(frozen=True, slots=True, eq=False)
class Variable:
    symbol: str
    prefix: Optional["Prefix"] = None
    vid: int = 0
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_hash", hash((self.symbol, self.prefix, self.vid)))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is Variable
            and self._hash == other._hash
            and self.symbol == other.symbol
            and self.prefix == other.prefix
            and self.vid == other.vid
        )

    @property
    def is_ground(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.symbol


@dataclass(frozen=True, slots=True, eq=False)
class Function:
    symbol: str
    args: Tuple["Term", ...] = ()
    prefix: Optional["Prefix"] = None
    _is_ground: bool = field(init=False, compare=False, repr=False)
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        prefix_is_ground = self.prefix is None or self.prefix.is_ground
        object.__setattr__(
            self,
            "_is_ground",
            prefix_is_ground
            and (not self.args or all(arg.is_ground for arg in self.args)),
        )
        object.__setattr__(self, "_hash", hash((self.symbol, self.args, self.prefix)))

    @property
    def is_ground(self) -> bool:
        return self._is_ground

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is Function
            and self._hash == other._hash
            and self.symbol == other.symbol
            and self.args == other.args
            and self.prefix == other.prefix
        )

    def __str__(self) -> str:
        if not self.args:
            return self.symbol
        return f"{self.symbol}({','.join(str(arg) for arg in self.args)})"


Term: TypeAlias = Union[Variable, Function]


@dataclass(frozen=True, slots=True, eq=False)
class Prefix:
    parts: Tuple[Term, ...] = ()
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_hash", hash(self.parts))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is Prefix
            and self._hash == other._hash
            and self.parts == other.parts
        )

    def __iter__(self):
        return iter(self.parts)

    def __len__(self) -> int:
        return len(self.parts)

    @property
    def is_ground(self) -> bool:
        return all(part.is_ground for part in self.parts)

    def __str__(self) -> str:
        return "[" + ",".join(str(part) for part in self.parts) + "]"


@dataclass(frozen=True, slots=True, eq=False)
class Atom:
    symbol: str
    args: Tuple[Term, ...] = ()
    _is_ground: bool = field(init=False, compare=False, repr=False)
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_is_ground", all(arg.is_ground for arg in self.args))
        object.__setattr__(self, "_hash", hash((self.symbol, self.args)))

    @property
    def is_ground(self) -> bool:
        return self._is_ground

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is Atom
            and self._hash == other._hash
            and self.symbol == other.symbol
            and self.args == other.args
        )

    def __str__(self) -> str:
        if not self.args:
            return self.symbol
        return f"{self.symbol}({','.join(str(arg) for arg in self.args)})"


@dataclass(frozen=True)
class Eq:
    left: Term
    right: Term


@dataclass(frozen=True)
class Not:
    formula: Formula


@dataclass(frozen=True)
class And:
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Or:
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Impl:
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Iff:
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Forall:
    variable: Variable
    body: Formula


@dataclass(frozen=True)
class Exists:
    variable: Variable
    body: Formula


@dataclass(frozen=True)
class Box:
    body: Formula
    index: Term | None = None


@dataclass(frozen=True)
class Diamond:
    body: Formula
    index: Term | None = None


@dataclass(frozen=True)
class Prefixed:
    formula: Formula
    prefix: Prefix


Formula: TypeAlias = Union[
    Atom,
    Eq,
    Not,
    And,
    Or,
    Impl,
    Iff,
    Forall,
    Exists,
    Box,
    Diamond,
    Prefixed,
]
