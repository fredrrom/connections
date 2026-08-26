"""Static matrix tier of the connection graph: the task embedding's input.

Built once per (matrix, start clauses) and reused for every decision of
every rollout that shares them. Ground terms and atoms are hash-consed
globally so that P(a) and -P(a) share one atom node; non-ground terms are
interned per clause, because a variable's scope is its clause and merging
same-named variables across clauses would fabricate couplings.
"""

from __future__ import annotations

import itertools
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from connections.syntax.formula import Atom, Function, Term, Variable
from connections.syntax.matrix import Matrix

from imitation.representation.schema import arg_position_bucket

_SYMBOL_KIND_PREDICATE = 0
_SYMBOL_KIND_FUNCTION = 1
_SYMBOL_KIND_CONSTANT = 2

_ROLE_INDEX = {"axiom": 0, "conjecture": 1}

_MATRIX_KEY_COUNTER = itertools.count()

_MATRIX_GRAPH_CACHE_MAX = 8
# Values keep a strong reference to their matrix: the key uses id(), and a
# collected matrix's id can be recycled by a new one, so an entry must pin
# the object its key describes for as long as it is cached.
_MATRIX_GRAPH_CACHE: OrderedDict[
    tuple[int, tuple[int, ...]], tuple[Matrix, "MatrixGraph"]
] = OrderedDict()


@dataclass(slots=True)
class MatrixGraph:
    """Node/edge lists for the static tier plus lookup indices."""

    nodes: dict[str, list[list[int]]] = field(
        default_factory=lambda: {
            "symbol": [],
            "clause": [],
            "literal": [],
            "term": [],
            "var": [],
        }
    )
    edges: dict[str, list[list[int]]] = field(
        default_factory=lambda: {
            "contains": [],
            "atom": [],
            "arg_term": [],
            "arg_var": [],
            "sym": [],
            "lit_sym": [],
            "complement": [],
        }
    )
    literal_index: dict[tuple[int, int], int] = field(default_factory=dict)
    # Cross-process-safe identity: collated batches share matrix tiers by
    # this key, and examples may be collected by different worker processes,
    # where id() values can collide across different problems.
    key: str = field(
        default_factory=lambda: f"{os.getpid()}:{next(_MATRIX_KEY_COUNTER)}"
    )
    _symbol_index: dict[tuple[str, int], int] = field(default_factory=dict)
    _term_index: dict[tuple[Any, ...], int] = field(default_factory=dict)
    _var_index: dict[tuple[int, Variable], int] = field(default_factory=dict)


def matrix_graph(matrix: Matrix, start_clause_ids: tuple[int, ...]) -> MatrixGraph:
    key = (id(matrix), tuple(start_clause_ids))
    cached = _MATRIX_GRAPH_CACHE.get(key)
    if cached is not None and cached[0] is matrix:
        _MATRIX_GRAPH_CACHE.move_to_end(key)
        return cached[1]
    graph = _build_matrix_graph(matrix, frozenset(start_clause_ids))
    _MATRIX_GRAPH_CACHE[key] = (matrix, graph)
    while len(_MATRIX_GRAPH_CACHE) > _MATRIX_GRAPH_CACHE_MAX:
        _MATRIX_GRAPH_CACHE.popitem(last=False)
    return graph


def _build_matrix_graph(
    matrix: Matrix, start_clause_ids: frozenset[int]
) -> MatrixGraph:
    graph = MatrixGraph()
    for clause_idx, clause in enumerate(matrix.clauses):
        clause_node = len(graph.nodes["clause"])
        graph.nodes["clause"].append(
            [
                min(clause.literal_count - 1, 4),
                _ROLE_INDEX.get(str(clause.role), 2),
                int(bool(clause.is_ground)),
                int(clause_idx in start_clause_ids),
            ]
        )
        for lit_idx, literal in enumerate(clause.literals):
            literal_node = len(graph.nodes["literal"])
            graph.nodes["literal"].append([int(literal.polarity)])
            graph.literal_index[(clause_idx, lit_idx)] = literal_node
            graph.edges["contains"].append([clause_node, literal_node])

            atom_node = _intern_atom(graph, literal.atom, clause_idx)
            graph.edges["atom"].append([literal_node, atom_node])
            graph.edges["lit_sym"].append(
                [
                    literal_node,
                    _intern_symbol(
                        graph,
                        literal.atom.symbol,
                        kind=_SYMBOL_KIND_PREDICATE,
                        arity=len(literal.atom.args),
                    ),
                ]
            )

    for (clause_idx, lit_idx), literal_node in graph.literal_index.items():
        for other in matrix.complements(clause_idx, lit_idx):
            graph.edges["complement"].append([literal_node, graph.literal_index[other]])
    return graph


def _intern_atom(graph: MatrixGraph, atom: Atom, clause_idx: int) -> int:
    # Non-ground structure is clause-scoped (variable scope), ground is global.
    scope = -1 if atom.is_ground else clause_idx
    key = ("atom", scope, atom)
    found = graph._term_index.get(key)
    if found is not None:
        return found
    node = len(graph.nodes["term"])
    graph.nodes["term"].append([int(atom.is_ground)])
    graph._term_index[key] = node
    graph.edges["sym"].append(
        [
            node,
            _intern_symbol(
                graph,
                atom.symbol,
                kind=_SYMBOL_KIND_PREDICATE,
                arity=len(atom.args),
            ),
        ]
    )
    _intern_args(graph, node, atom.args, clause_idx)
    return node


def _intern_term(graph: MatrixGraph, term: Function, clause_idx: int) -> int:
    scope = -1 if term.is_ground else clause_idx
    key = ("term", scope, term)
    found = graph._term_index.get(key)
    if found is not None:
        return found
    node = len(graph.nodes["term"])
    graph.nodes["term"].append([int(term.is_ground)])
    graph._term_index[key] = node
    kind = _SYMBOL_KIND_CONSTANT if not term.args else _SYMBOL_KIND_FUNCTION
    graph.edges["sym"].append(
        [node, _intern_symbol(graph, term.symbol, kind=kind, arity=len(term.args))]
    )
    _intern_args(graph, node, term.args, clause_idx)
    return node


def _intern_args(
    graph: MatrixGraph,
    parent_node: int,
    args: tuple[Term, ...],
    clause_idx: int,
) -> None:
    for position, arg in enumerate(args):
        bucket = arg_position_bucket(position)
        if isinstance(arg, Variable):
            graph.edges["arg_var"].append(
                [parent_node, _intern_var(graph, arg, clause_idx), bucket]
            )
        else:
            graph.edges["arg_term"].append(
                [parent_node, _intern_term(graph, arg, clause_idx), bucket]
            )


def _intern_var(graph: MatrixGraph, variable: Variable, clause_idx: int) -> int:
    key = (clause_idx, variable)
    found = graph._var_index.get(key)
    if found is not None:
        return found
    node = len(graph.nodes["var"])
    graph.nodes["var"].append([0])
    graph._var_index[key] = node
    return node


def _intern_symbol(graph: MatrixGraph, symbol: str, *, kind: int, arity: int) -> int:
    key = (symbol, kind)
    found = graph._symbol_index.get(key)
    if found is not None:
        return found
    node = len(graph.nodes["symbol"])
    graph.nodes["symbol"].append([kind, min(arity, 4)])
    graph._symbol_index[key] = node
    return node


__all__ = ["MatrixGraph", "matrix_graph"]
