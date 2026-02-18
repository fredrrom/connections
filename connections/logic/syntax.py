from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


def _render_symbol(
    name: str, args: Tuple["Term", ...], prefix: Optional["Prefix"]
) -> str:
    if args:
        base = f"{name}({', '.join(str(arg) for arg in args)})"
    else:
        base = name
    if prefix is None:
        return base
    return f"{base}:{prefix}"


@dataclass(frozen=True)
class Term:
    name: str
    args: Tuple["Term", ...] = ()
    prefix: Optional["Prefix"] = None

    def __str__(self) -> str:
        return _render_symbol(self.name, self.args, self.prefix)


@dataclass(frozen=True)
class Variable(Term):
    vid: int = 0

    def __str__(self) -> str:
        if self.vid == 0:
            return self.name
        return f"{self.name}{self.vid}"


@dataclass(frozen=True)
class Constant(Term):
    pass


@dataclass(frozen=True)
class Function(Term):
    pass


@dataclass(frozen=True)
class Prefix:
    parts: Tuple[Term, ...] = ()

    def __iter__(self):
        return iter(self.parts)

    def __len__(self) -> int:
        return len(self.parts)

    def __str__(self) -> str:
        if not self.parts:
            return "<>"
        return "<" + ", ".join(str(part) for part in self.parts) + ">"


@dataclass(frozen=True)
class Literal:
    name: str
    args: Tuple[Term, ...] = ()
    prefix: Optional["Prefix"] = None
    neg: bool = False

    def __str__(self) -> str:
        rendered = _render_symbol(self.name, self.args, self.prefix)
        return f"-{rendered}" if self.neg else rendered


@dataclass(frozen=True)
class Clause:
    literals: Tuple[Literal, ...]

    def __iter__(self):
        return iter(self.literals)

    def __len__(self) -> int:
        return len(self.literals)


@dataclass(frozen=True)
class Matrix:
    clauses: Tuple[Clause, ...]
    connection_graph: Dict[Tuple[bool, str], Tuple[Tuple[int, int], ...]] = field(
        init=False, repr=False
    )
    positive_clauses: Tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        connection_graph: Dict[Tuple[bool, str], List[Tuple[int, int]]] = {}
        positive: List[int] = []
        for clause_idx, clause in enumerate(self.clauses):
            is_positive = True
            for lit_idx, lit in enumerate(clause.literals):
                key = (not lit.neg, lit.name)
                connection_graph.setdefault(key, []).append((clause_idx, lit_idx))
                if lit.neg:
                    is_positive = False
            if is_positive:
                positive.append(clause_idx)
        object.__setattr__(
            self,
            "connection_graph",
            {key: tuple(value) for key, value in connection_graph.items()},
        )
        object.__setattr__(self, "positive_clauses", tuple(positive))

    def complements(self, literal: Literal) -> Tuple[Tuple[int, int], ...]:
        return self.connection_graph.get((literal.neg, literal.name), ())

    def __getitem__(self, idx: Union[int, slice, Tuple[int, int]]) -> Any:
        if isinstance(idx, tuple) and len(idx) == 2:
            clause_idx, lit_idx = idx
            return self.clauses[clause_idx].literals[lit_idx]
        return self.clauses[idx]

    def __iter__(self):
        return iter(self.clauses)

    def __len__(self) -> int:
        return len(self.clauses)
