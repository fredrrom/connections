from __future__ import annotations

from dataclasses import dataclass

from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Matrix


@dataclass(frozen=True, slots=True)
class Problem:
    matrix: Matrix
    logic: Logic = "classical"
    domain: Domain = "constant"

    @property
    def has_conjecture(self) -> bool:
        return bool(self.matrix.source_has_conjecture)


__all__ = ["Problem"]
