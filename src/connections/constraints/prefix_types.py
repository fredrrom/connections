from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from connections.core.formula import Prefix, Variable


@dataclass(frozen=True, slots=True)
class PrefixBinding:
    variable: Variable
    target: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class PrefixEquation:
    left: Prefix
    right: Prefix


__all__ = ["PrefixBinding", "PrefixEquation"]
