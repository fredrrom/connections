from __future__ import annotations

import re

from connections.policy import DFSOptions, IterativeDeepeningOptions
from connections.prover.strategy import MatrixOptions
from connections.pycop.strategy import PycopStrategy


class LeancopSettingsCodec:
    """Encode/decode leanCoP-compatible strategy tokens for pycop schedules."""

    @staticmethod
    def to_tokens(strategy: PycopStrategy | None = None) -> list[str]:
        normalized = strategy if strategy is not None else PycopStrategy()
        tokens: list[str] = []

        if normalized.matrix.translation in {"def", "nodef"}:
            tokens.append(normalized.matrix.translation)
        if normalized.matrix.start_clauses == "conjecture":
            tokens.append("conj")
        if normalized.matrix.reorder > 0:
            tokens.append(f"reo({normalized.matrix.reorder})")

        if normalized.dfs.cut:
            tokens.append("cut")
        if normalized.dfs.scut:
            tokens.append("scut")
        if normalized.id.comp is not None:
            tokens.append(f"comp({normalized.id.comp})")

        return tokens

    @staticmethod
    def to_token_list(strategy: PycopStrategy | None = None) -> str:
        return f"[{','.join(LeancopSettingsCodec.to_tokens(strategy))}]"

    @staticmethod
    def from_tokens(tokens: list[str] | None) -> PycopStrategy:
        translation = "default"
        reorder = 0
        start_clauses = "positive"
        cut = False
        scut = False
        comp: int | None = None

        if tokens is None:
            return PycopStrategy()

        for token in tokens:
            if token == "nodef":
                translation = "nodef"
                continue
            if token == "def" and translation != "nodef":
                translation = "def"
                continue
            if token == "conj":
                start_clauses = "conjecture"
                continue

            match = re.fullmatch(r"reo\((\d+)\)", token)
            if match:
                reorder = int(match.group(1))
                continue

            if token == "cut":
                cut = True
                continue
            if token == "scut":
                scut = True
                continue

            match = re.fullmatch(r"comp\((\d+)\)", token)
            if match:
                comp = int(match.group(1))

        return PycopStrategy(
            matrix=MatrixOptions(
                translation=translation,
                reorder=reorder,
                start_clauses=start_clauses,
            ),
            dfs=DFSOptions(cut=cut, scut=scut, factorization="equal"),
            id=IterativeDeepeningOptions(comp=comp),
        )


__all__ = ["LeancopSettingsCodec"]
