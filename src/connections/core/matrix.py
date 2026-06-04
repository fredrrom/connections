from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Literal as TypingLiteral,
    Optional,
    Tuple,
    TypeAlias,
)

from connections.core.formula import Atom, Prefix, Variable
ClauseRole: TypeAlias = TypingLiteral["axiom", "conjecture"]
LiteralPosition: TypeAlias = tuple[int, int]
SignedPredicateSymbol: TypeAlias = tuple[bool, str]


@dataclass(frozen=True, slots=True, eq=False)
class Literal:
    atom: Atom
    prefix: Optional[Prefix] = None
    polarity: bool = True
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_hash",
            hash((self.atom, self.prefix, self.polarity)),
        )

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        return (
            type(other) is Literal
            and self._hash == other._hash
            and self.atom == other.atom
            and self.prefix == other.prefix
            and self.polarity == other.polarity
        )

    @property
    def signed_symbol(self) -> SignedPredicateSymbol:
        return (self.polarity, self.atom.symbol)

    @property
    def complement_symbol(self) -> SignedPredicateSymbol:
        return (not self.polarity, self.atom.symbol)

    @property
    def is_ground(self) -> bool:
        return self.atom.is_ground and (
            self.prefix is None or self.prefix.is_ground
        )

    def __str__(self) -> str:
        prefix = "" if self.polarity else "-"
        return f"{prefix}{self.atom}"


@dataclass(frozen=True)
class Clause:
    literals: Tuple[Literal, ...]
    role: ClauseRole = "axiom"
    free_variables: Tuple[Variable, ...] = ()
    is_ground: bool | None = None

    def __post_init__(self) -> None:
        if self.is_ground is None:
            is_ground = True
            for literal in self.literals:
                if not literal.is_ground:
                    is_ground = False
                    break
            object.__setattr__(self, "is_ground", is_ground)

    def __iter__(self):
        return iter(self.literals)

    def __len__(self) -> int:
        return self.literal_count

    @property
    def literal_count(self) -> int:
        return len(self.literals)

    def literal(self, index: int) -> Literal:
        return self.literals[index]

    def __str__(self) -> str:
        return "[" + ",".join(str(literal) for literal in self.literals) + "]"


@dataclass
class Matrix:
    clauses: Tuple[Clause, ...]
    source_has_conjecture: bool | None = None
    connection_graph: Dict[SignedPredicateSymbol, Tuple[LiteralPosition, ...]] = field(
        init=False, repr=False
    )
    statically_filtered_connection_graph: Dict[
        LiteralPosition, Tuple[LiteralPosition, ...]
    ] = field(init=False, repr=False)
    positive_clauses: Tuple[int, ...] = field(init=False, repr=False)
    conjecture_clauses: Tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.connection_graph = self._build_connection_graph()
        self.statically_filtered_connection_graph = {}
        self.positive_clauses = self._build_positive_clauses()
        self.conjecture_clauses = self._build_conjecture_clauses()
        if self.source_has_conjecture is None:
            self.source_has_conjecture = bool(self.conjecture_clauses)

    def _build_connection_graph(
        self,
    ) -> Dict[SignedPredicateSymbol, Tuple[LiteralPosition, ...]]:
        connection_graph: defaultdict[SignedPredicateSymbol, List[LiteralPosition]] = (
            defaultdict(list)
        )
        for clause_idx, clause in enumerate(self.clauses):
            for lit_idx, lit in enumerate(clause.literals):
                connection_graph[lit.signed_symbol].append((clause_idx, lit_idx))
        return {key: tuple(value) for key, value in connection_graph.items()}

    def _build_positive_clauses(self) -> Tuple[int, ...]:
        positive: List[int] = []
        for clause_idx, clause in enumerate(self.clauses):
            if all(lit.polarity for lit in clause.literals):
                positive.append(clause_idx)
        return tuple(positive)

    def _build_conjecture_clauses(self) -> Tuple[int, ...]:
        return tuple(
            idx
            for idx, clause in enumerate(self.clauses)
            if clause.role == "conjecture"
        )

    def complements(self, clause_idx: int, lit_idx: int) -> Tuple[LiteralPosition, ...]:
        key = (clause_idx, lit_idx)
        if key not in self.statically_filtered_connection_graph:
            literal = self.clauses[clause_idx].literals[lit_idx]
            self.statically_filtered_connection_graph[key] = (
                self._compatible_complements(literal)
            )
        return self.statically_filtered_connection_graph[key]

    def _compatible_complements(self, literal: Literal) -> Tuple[LiteralPosition, ...]:
        from connections.constraints.term import TermSubstitution

        candidates = self.connection_graph.get(literal.complement_symbol, ())
        if not candidates:
            return ()
        return tuple(
            (clause_idx, lit_idx)
            for clause_idx, lit_idx in candidates
            if TermSubstitution.unifiable_from_empty(
                older=literal,
                newer=self.clauses[clause_idx].literals[lit_idx],
            )
        )

    def __getitem__(self, idx: int | slice | Tuple[int, int]) -> Any:
        if isinstance(idx, tuple) and len(idx) == 2:
            clause_idx, lit_idx = idx
            return self.clauses[clause_idx].literals[lit_idx]
        return self.clauses[idx]

    def __iter__(self):
        return iter(self.clauses)

    def __len__(self) -> int:
        return len(self.clauses)
