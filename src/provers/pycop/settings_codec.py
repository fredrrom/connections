from __future__ import annotations

import re

from collections.abc import Mapping
from typing import Any, cast

from connections.policy import FirstActionIDPolicy
from connections.prover.strategy import (
    MatrixOptions,
    PolicyOptions,
    Strategy,
)


class LeancopSettingsCodec:
    """Encode/decode leanCoP-compatible strategy tokens for pycop schedules."""

    @staticmethod
    def to_tokens(strategy: Strategy | None = None) -> list[str]:
        normalized = strategy if strategy is not None else LeancopSettingsCodec.from_tokens(None)
        matrix = normalized.matrix
        args = _policy_args(normalized)
        tokens: list[str] = []

        if matrix.translation in {"def", "nodef"}:
            tokens.append(matrix.translation)
        if matrix.start_clauses == "conjecture":
            tokens.append("conj")
        if matrix.reorder > 0:
            tokens.append(f"reo({matrix.reorder})")

        if args.get("cut", False):
            tokens.append("cut")
        if args.get("scut", False):
            tokens.append("scut")
        if args.get("comp") is not None:
            tokens.append(f"comp({args['comp']})")

        return tokens

    @staticmethod
    def to_token_list(strategy: Strategy | None = None) -> str:
        return f"[{','.join(LeancopSettingsCodec.to_tokens(strategy))}]"

    @staticmethod
    def from_tokens(tokens: list[str] | None) -> Strategy:
        translation = "default"
        reorder = 0
        start_clauses = "positive"
        cut = False
        scut = False
        comp: int | None = None

        if tokens is None:
            return Strategy(
                matrix=MatrixOptions(),
                policy=PolicyOptions(
                    policy_class=FirstActionIDPolicy,
                    args=_leancop_policy_args(),
                ),
            )

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

        return Strategy(
            matrix=MatrixOptions(
                translation=translation,
                reorder=reorder,
                start_clauses=start_clauses,
            ),
            policy=PolicyOptions(
                policy_class=FirstActionIDPolicy,
                args=_leancop_policy_args(cut=cut, scut=scut, comp=comp),
            ),
        )


def _leancop_policy_args(
    *,
    cut: bool = False,
    scut: bool = False,
    comp: int | None = None,
) -> dict[str, object]:
    return {
        "cut": cut,
        "scut": scut,
        "comp": comp,
        "factorization": "equal",
    }


def _policy_args(strategy: Strategy) -> Mapping[str, Any]:
    if strategy.policy.policy_class is not FirstActionIDPolicy:
        raise TypeError("leanCoP settings codec requires FirstActionIDPolicy strategy")
    return cast(Mapping[str, Any], strategy.policy.args or {})


__all__ = ["LeancopSettingsCodec"]
