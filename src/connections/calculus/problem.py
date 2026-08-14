from __future__ import annotations

from dataclasses import dataclass, field

from connections.clausification import StartClausesMode
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Matrix


@dataclass(frozen=True, slots=True)
class Problem:
    matrix: Matrix
    start_clauses: StartClausesMode
    logic: Logic = "classical"
    domain: Domain = "constant"
    start_clause_ids: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.start_clauses == "conjecture":
            start_clause_ids = (
                self.matrix.conjecture_clauses or self.matrix.positive_clauses
            )
            object.__setattr__(self, "start_clause_ids", start_clause_ids)
            return
        object.__setattr__(self, "start_clause_ids", self.matrix.positive_clauses)

    @property
    def has_conjecture(self) -> bool:
        return bool(self.matrix.source_has_conjecture)


__all__ = ["Problem"]
