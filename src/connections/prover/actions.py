from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from connections.prover.rules import (
    Extension,
    Factorization,
    Reduction,
    Rule,
    Start,
)

RuleT = TypeVar("RuleT", bound=Rule)


@dataclass(frozen=True, slots=True)
class ApplyAction(Generic[RuleT]):
    goal_id: int
    rule: RuleT

    def trace_event(self) -> str:
        if isinstance(self.rule, Start):
            return "start"
        if isinstance(self.rule, Extension):
            return "extension"
        if isinstance(self.rule, Reduction):
            return "reduction"
        if isinstance(self.rule, Factorization):
            return "lemma" if self.rule.mode == "equal" else "factorization"
        raise TypeError(f"unsupported action: {self!r}")

    def __str__(self) -> str:
        if isinstance(self.rule, Start):
            if self.rule.clause_idx is None:
                return f"start({self.rule.clause})"
            return f"start({self.rule.clause},source={self.rule.clause_idx})"
        if isinstance(self.rule, Extension):
            literal = self.rule.clause.literal(self.rule.lit_idx)
            if self.rule.clause_idx is None:
                return f"extension({literal})"
            rest = tuple(
                lit
                for idx, lit in enumerate(self.rule.clause)
                if idx != self.rule.lit_idx
            )
            return (
                f"extension({literal},"
                f"source={self.rule.clause_idx}:{self.rule.lit_idx},"
                f"rest={[str(lit) for lit in rest]})"
            )
        if isinstance(self.rule, Reduction):
            return f"reduction(source_goal={self.rule.source_goal_id})"
        if isinstance(self.rule, Factorization):
            name = "lemma" if self.rule.mode == "equal" else "factorization"
            return f"{name}(source_goal={self.rule.source_goal_id})"
        raise TypeError(f"unsupported action: {self!r}")


@dataclass(frozen=True, slots=True)
class UndoAction:
    step_id: int

    def trace_event(self) -> str:
        return "backtrack"

    def __str__(self) -> str:
        return f"backtrack(step={self.step_id})"


StartAction: TypeAlias = ApplyAction[Start]
FactorizationAction: TypeAlias = ApplyAction[Factorization]
ReductionAction: TypeAlias = ApplyAction[Reduction]
ExtensionAction: TypeAlias = ApplyAction[Extension]
AnyApplyAction: TypeAlias = (
    StartAction | FactorizationAction | ReductionAction | ExtensionAction
)
Action: TypeAlias = AnyApplyAction | UndoAction


@dataclass(frozen=True, slots=True)
class ApplyActions:
    start: tuple[StartAction, ...] = ()
    factorization: tuple[FactorizationAction, ...] = ()
    reduction: tuple[ReductionAction, ...] = ()
    extension: tuple[ExtensionAction, ...] = ()

    def __bool__(self) -> bool:
        return bool(
            self.start or self.factorization or self.reduction or self.extension
        )

    def ordered(self) -> tuple[AnyApplyAction, ...]:
        return self.start + self.factorization + self.reduction + self.extension


__all__ = [
    "Action",
    "AnyApplyAction",
    "ApplyAction",
    "ApplyActions",
    "ExtensionAction",
    "FactorizationAction",
    "ReductionAction",
    "StartAction",
    "UndoAction",
]
