from __future__ import annotations

from dataclasses import dataclass, field

from connections.syntax.formula import Variable
from connections.constraints.prefix import PrefixEquation
from connections.constraints.term import TermBinding

FreeVariableReference = tuple[Variable, int | None]


@dataclass(frozen=True, slots=True)
class ConstraintDelta:
    term_bindings: tuple[TermBinding, ...] = field(default_factory=tuple)
    prefix_equations: tuple[PrefixEquation, ...] = field(default_factory=tuple)
    free_variables: tuple[FreeVariableReference, ...] = field(default_factory=tuple)

    def __bool__(self) -> bool:
        return bool(
            self.term_bindings or self.prefix_equations or self.free_variables
        )


def term_delta(bindings: tuple[TermBinding, ...]) -> ConstraintDelta:
    return ConstraintDelta(term_bindings=bindings)


def prefix_delta(equations: tuple[PrefixEquation, ...]) -> ConstraintDelta:
    return ConstraintDelta(prefix_equations=equations)


def free_variable_delta(
    free_variables: tuple[FreeVariableReference, ...],
) -> ConstraintDelta:
    return ConstraintDelta(free_variables=free_variables)


EMPTY_CONSTRAINT_DELTA = ConstraintDelta()


__all__ = [
    "ConstraintDelta",
    "EMPTY_CONSTRAINT_DELTA",
    "FreeVariableReference",
    "free_variable_delta",
    "prefix_delta",
    "term_delta",
]
