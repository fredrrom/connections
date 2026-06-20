from __future__ import annotations

from typing import Literal, TypeAlias

Logic: TypeAlias = Literal["classical", "intuitionistic", "D", "T", "S4", "S5"]
Domain: TypeAlias = Literal["constant", "cumulative", "varying"]

CLASSICAL_LOGICS = frozenset({"classical"})
INTUITIONISTIC_LOGICS = frozenset({"intuitionistic", "intu"})
MODAL_LOGICS = frozenset({"d", "t", "s4", "s5"})
SUPPORTED_DOMAINS = frozenset(
    {"constant", "cumulative", "varying", "const", "cumul", "vary"}
)


def normalize_logic(logic: str) -> str:
    return logic.lower()


def normalize_domain(domain: str) -> str:
    normalized = domain.lower()
    if normalized == "constant":
        return "const"
    if normalized == "cumulative":
        return "cumul"
    if normalized == "varying":
        return "vary"
    return normalized


__all__ = [
    "CLASSICAL_LOGICS",
    "Domain",
    "INTUITIONISTIC_LOGICS",
    "Logic",
    "MODAL_LOGICS",
    "SUPPORTED_DOMAINS",
    "normalize_domain",
    "normalize_logic",
]
