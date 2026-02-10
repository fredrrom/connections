from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import weakref

from connections.logic.syntax import (
    Clause,
    Constant,
    Function,
    Literal,
    Prefix,
    Term,
    Variable,
)


@dataclass(frozen=True, slots=True)
class VarFactory:
    _next_id: int = 1

    def fresh(self, name: str, prefix: Optional[Prefix] = None) -> Variable:
        vid = self._next_id
        object.__setattr__(self, "_next_id", vid + 1)
        return Variable(name, prefix=prefix, vid=vid)


class ClauseFactory:
    def __init__(
        self,
        term_factory: Optional[VarFactory] = None,
        prefix_factory: Optional[VarFactory] = None,
    ) -> None:
        self.term_factory = term_factory or VarFactory()
        self.prefix_factory = prefix_factory or self.term_factory

    def freshen_clause(self, clause: Clause) -> Tuple[Literal, ...]:
        term_map: Dict[Variable, Variable] = {}
        prefix_map: Dict[Variable, Variable] = {}
        return tuple(
            self._freshen_literal(literal, term_map, prefix_map)
            for literal in clause.literals
        )

    def _freshen_literal(
        self,
        literal: Literal,
        term_map: Dict[Variable, Variable],
        prefix_map: Dict[Variable, Variable],
    ) -> Literal:
        args = tuple(
            self._freshen_term(arg, term_map, self.term_factory) for arg in literal.args
        )
        prefix = None
        if literal.prefix is not None:
            prefix = self._freshen_prefix(
                literal.prefix, prefix_map, self.prefix_factory
            )
        return Literal(literal.name, args=args, prefix=prefix, neg=literal.neg)

    def _freshen_prefix(
        self,
        prefix: Prefix,
        mapping: Dict[Variable, Variable],
        factory: VarFactory,
    ) -> Prefix:
        return Prefix(
            tuple(self._freshen_term(part, mapping, factory) for part in prefix.parts)
        )

    def _freshen_term(
        self,
        term: Term,
        mapping: Dict[Variable, Variable],
        factory: VarFactory,
    ) -> Term:
        if isinstance(term, Variable):
            if term not in mapping:
                mapping[term] = factory.fresh(term.name, prefix=term.prefix)
            return mapping[term]
        if term.args:
            args = tuple(self._freshen_term(arg, mapping, factory) for arg in term.args)
            return type(term)(term.name, args=args, prefix=term.prefix)
        return term


_VAR_POOL: "weakref.WeakValueDictionary[Tuple[str, int, Optional[Prefix]], Variable]" = weakref.WeakValueDictionary()
_CONST_POOL: "weakref.WeakValueDictionary[str, Constant]" = (
    weakref.WeakValueDictionary()
)
_FUNC_POOL: "weakref.WeakValueDictionary[Tuple[str, Tuple[Term, ...], Optional[Prefix]], Function]" = weakref.WeakValueDictionary()
_LIT_POOL: "weakref.WeakValueDictionary[Tuple[str, Tuple[Term, ...], Optional[Prefix], bool], Literal]" = weakref.WeakValueDictionary()


def intern_variable(
    name: str, vid: int = 0, prefix: Optional[Prefix] = None
) -> Variable:
    key = (name, vid, prefix)
    existing = _VAR_POOL.get(key)
    if existing is not None:
        return existing
    var = Variable(name, vid=vid, prefix=prefix)
    _VAR_POOL[key] = var
    return var


def intern_constant(name: str) -> Constant:
    existing = _CONST_POOL.get(name)
    if existing is not None:
        return existing
    const = Constant(name)
    _CONST_POOL[name] = const
    return const


def intern_function(
    name: str,
    args: Tuple[Term, ...],
    prefix: Optional[Prefix] = None,
) -> Function:
    key = (name, args, prefix)
    existing = _FUNC_POOL.get(key)
    if existing is not None:
        return existing
    func = Function(name, args=args, prefix=prefix)
    _FUNC_POOL[key] = func
    return func


def intern_literal(
    name: str,
    args: Tuple[Term, ...],
    prefix: Optional[Prefix] = None,
    neg: bool = False,
) -> Literal:
    key = (name, args, prefix, neg)
    existing = _LIT_POOL.get(key)
    if existing is not None:
        return existing
    lit = Literal(name, args=args, prefix=prefix, neg=neg)
    _LIT_POOL[key] = lit
    return lit
