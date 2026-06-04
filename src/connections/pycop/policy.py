from __future__ import annotations

from connections.core.status import ProverOutcome
from connections.policy import (
    BacktrackGranularity,
    IterativeDeepeningPolicy,
    PolicyOutput,
)
from connections.prover.rules import FactorizationMode
from connections.prover.state import State
from connections.trace_logging import trace, trace_logger
from connections.pycop.strategy import PycopStrategy


class PycopPolicy(IterativeDeepeningPolicy):
    def __init__(
        self,
        strategy: PycopStrategy | None = None,
        *,
        cut: bool | None = None,
        scut: bool | None = None,
        comp: int | None = None,
        backtrack: BacktrackGranularity | None = None,
        factorization: FactorizationMode | None = None,
        initial_depth: int | None = None,
    ) -> None:
        if strategy is not None:
            cut = strategy.dfs.cut if cut is None else cut
            scut = strategy.dfs.scut if scut is None else scut
            comp = strategy.id.comp if comp is None else comp
            backtrack = strategy.dfs.backtrack if backtrack is None else backtrack
            factorization = (
                strategy.dfs.factorization
                if factorization is None
                else factorization
            )
            initial_depth = (
                strategy.id.initial_depth
                if initial_depth is None
                else initial_depth
            )
        super().__init__(
            cut=False if cut is None else cut,
            scut=False if scut is None else scut,
            comp=comp,
            backtrack="step" if backtrack is None else backtrack,
            factorization="equal" if factorization is None else factorization,
            initial_depth=1 if initial_depth is None else initial_depth,
        )

    def __call__(self, state: State) -> PolicyOutput:
        if not state.problem.matrix.clauses:
            self._trace_empty_matrix_leancop_choicepoints()
            return ProverOutcome.ID_FIXED_POINT
        return super().__call__(state)

    def _trace_empty_matrix_leancop_choicepoints(self) -> None:
        """Mirror leanCoP's empty-matrix trace quirk without changing state.

        leanCoP re-clausifies `[]` into failed start choicepoints. pycop keeps
        `Matrix(())` semantic, so these events are trace-only.
        """
        if self.comp is None:
            self._trace_empty_matrix_round(scut=self.scut_enabled)
            return

        for depth in range(1, self.comp + 1):
            self._trace_empty_matrix_round(scut=self.scut_enabled)
            if depth < self.comp:
                trace(trace_logger, "pathlim")
        self._trace_empty_matrix_round(scut=False)

    @staticmethod
    def _trace_empty_matrix_round(*, scut: bool) -> None:
        if scut:
            trace(trace_logger, "scut")
        trace(trace_logger, "start")
        trace(trace_logger, "backtrack")


__all__ = [
    "PycopPolicy",
]
