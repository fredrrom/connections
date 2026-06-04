from __future__ import annotations

from dataclasses import dataclass, field

from connections.policy import DFSOptions, IterativeDeepeningOptions
from connections.prover.strategy import MatrixOptions


@dataclass(frozen=True, slots=True)
class PycopStrategy:
    matrix: MatrixOptions = field(default_factory=MatrixOptions)
    dfs: DFSOptions = field(
        default_factory=lambda: DFSOptions(factorization="equal")
    )
    id: IterativeDeepeningOptions = field(
        default_factory=IterativeDeepeningOptions
    )

    def create_policy(self):
        from connections.pycop.policy import PycopPolicy

        return PycopPolicy(self)


__all__ = [
    "PycopStrategy",
]
