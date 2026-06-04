from __future__ import annotations

from typing import Literal as TypingLiteral, Sequence

from connections.trace_logging import TRACE_LEVEL, clausification_trace_logger, trace
from connections.clausification.conversion import (
    cnf_formula_to_literals as _cnf_formula_to_literals,
    dnf,
    free_variables_for_literals as _free_variables_for_literals,
    is_literal as _is_literal,
    mat as _mat,
    prefixed_dnf as _prefixed_dnf,
    prefixed_mat as _prefixed_mat,
)
from connections.clausification.equality import add_equality_axioms
from connections.core.formula import (
    And,
    Atom,
    Box,
    Diamond,
    Eq,
    Exists,
    Forall,
    Formula,
    Function,
    Iff,
    Impl,
    Not,
    Or,
    Prefixed,
    Prefix,
    Term,
    Variable,
)
from connections.clausification.formula_ops import (
    contains_modal_formula,
    substitute_variable,
    univar,
)
from connections.core.logic import (
    CLASSICAL_LOGICS,
    INTUITIONISTIC_LOGICS,
    MODAL_LOGICS,
    normalize_logic,
)
from connections.core.matrix import Clause, ClauseRole, Literal, Matrix
from connections.clausification.reorder import mreorder_items
from connections.parsing.tptp.parser import ParsedTPTPDocument

ClausificationTranslationMode = TypingLiteral["default", "def", "nodef"]
StartClausesMode = TypingLiteral["positive", "conjecture"]
_CONJECTURE_CNF_ROLES = {"conjecture", "negated_conjecture"}


def clausify(
    ast: Formula | ParsedTPTPDocument,
    *,
    translation: ClausificationTranslationMode = "default",
    reorder: int = 0,
    start_clauses: StartClausesMode = "positive",
    logic: str = "classical",
) -> Matrix:
    if isinstance(ast, ParsedTPTPDocument):
        return make_matrix_from_document(
            ast,
            translation=translation,
            reorder=reorder,
            start_clauses=start_clauses,
            logic=logic,
        )
    return make_matrix_from_formula(
        ast,
        translation=translation,
        reorder=reorder,
        logic=logic,
    )


def make_matrix_from_document(
    document: ParsedTPTPDocument,
    *,
    translation: ClausificationTranslationMode = "default",
    reorder: int = 0,
    start_clauses: StartClausesMode = "positive",
    logic: str = "classical",
) -> Matrix:
    from connections.parsing.tptp.transformer import StmtCNF

    _trace(
        "clausification.document.start",
        statements=len(document.statements),
    )
    if document.statements and all(
        isinstance(statement, StmtCNF) for statement in document.statements
    ):
        return make_matrix_from_cnf_statements(
            tuple(document.statements),
            reorder=reorder,
        )
    if any(isinstance(statement, StmtCNF) for statement in document.statements):
        raise NotImplementedError(
            "mixed CNF and non-CNF matrix construction is not yet supported."
        )
    if document.problem_formula is None:
        _trace("clausification.document.empty")
        return Matrix(())

    axiom_count = 0
    conjecture_count = 0
    for statement in document.statements:
        role = statement.role
        if role == "conjecture":
            conjecture_count += 1
        else:
            axiom_count += 1
    _trace(
        "clausification.document.roles",
        axioms=axiom_count,
        conjectures=conjecture_count,
    )

    normalized_logic = normalize_logic(logic)
    if document.conjecture_formula is not None:
        combined = document.problem_formula
        if document.axiom_formula is not None:
            combine_mode = "axioms_imply_conjectures"
        else:
            combine_mode = "conjectures"
    elif normalized_logic in INTUITIONISTIC_LOGICS:
        combined = Impl(document.problem_formula, Atom("false___"))
        combine_mode = "axioms_imply_false"
    else:
        combined = Not(document.problem_formula)
        combine_mode = "negated_axioms"
    _trace("clausification.document.combine", mode=combine_mode)

    if start_clauses == "conjecture" and isinstance(combined, Impl):
        mark_conjecture_clauses = True
        marker = Atom("#")
        combined = Impl(And(combined.left, marker), And(marker, combined.right))
    else:
        mark_conjecture_clauses = False

    matrix = make_matrix_from_formula(
        combined,
        translation=translation,
        reorder=reorder,
        mark_conjecture_clauses=mark_conjecture_clauses,
        logic=logic,
    )
    matrix.source_has_conjecture = document.conjecture_formula is not None
    return matrix


def make_matrix_from_cnf_statements(
    statements: Sequence[object],
    *,
    reorder: int = 0,
) -> Matrix:
    from connections.parsing.tptp.transformer import StmtCNF

    _trace(
        "clausification.cnf.start",
        statements=len(statements),
    )
    clauses: list[Clause] = []
    for statement in statements:
        if not isinstance(statement, StmtCNF):
            raise TypeError(f"expected StmtCNF, got {type(statement)!r}")
        role = _cnf_clause_role(statement.role)
        literals = tuple(_cnf_formula_to_literals(statement.formula))
        clauses.append(
            Clause(
                literals,
                role,
                free_variables=_free_variables_for_literals(literals),
            )
        )
    if reorder > 0:
        clauses = mreorder_items(clauses, reorder)
        _trace("clausification.reorder", rounds=reorder)
    matrix = Matrix(tuple(clauses), source_has_conjecture=False)
    _trace(
        "clausification.cnf.done",
        clauses=len(matrix.clauses),
        literals=sum(len(clause) for clause in matrix.clauses),
    )
    return matrix


def make_matrix_from_formula(
    formula: Formula,
    *,
    translation: ClausificationTranslationMode = "default",
    reorder: int = 0,
    mark_conjecture_clauses: bool = False,
    logic: str = "classical",
) -> Matrix:
    normalized_logic = normalize_logic(logic)
    if normalized_logic not in CLASSICAL_LOGICS:
        return make_nonclassical_matrix_from_formula(
            formula,
            translation=translation,
            reorder=reorder,
            mark_conjecture_clauses=mark_conjecture_clauses,
            logic=logic,
        )
    if contains_modal_formula(formula):
        raise NotImplementedError(
            "classical clausification rejects modal formulas; select a modal logic."
        )
    _trace(
        "clausification.formula.start",
        translation=translation,
        reorder=reorder,
    )
    with_equality = add_equality_axioms(formula)
    _trace(
        "clausification.equality_axioms",
        added=with_equality is not formula,
    )
    formula = with_equality
    formula = univar(formula)
    _trace("clausification.univar")

    if translation == "nodef":
        nnf, _ = def_nnf(formula, mode="nnf")
        _trace("clausification.def_nnf", mode="nnf")
        dnf_formula = dnf(nnf)
        _trace("clausification.dnf")
    elif translation != "def" and isinstance(formula, Impl):
        nnf_left, next_index = def_nnf(Not(formula.left), mode="nnf")
        _trace("clausification.def_nnf", mode="nnf", side="left")
        dnf_left = dnf(nnf_left)
        _trace("clausification.dnf", side="left")
        dnf_right, _ = def_nnf(formula.right, start_index=next_index, mode="def")
        _trace("clausification.def_nnf", mode="def", side="right")
        dnf_formula = Or(dnf_right, dnf_left)
    else:
        dnf_formula, _ = def_nnf(formula, mode="def")
        _trace("clausification.def_nnf", mode="def")

    matrix_clauses = _mat(dnf_formula)
    _trace(
        "clausification.mat",
        clauses=len(matrix_clauses),
        literals=sum(len(clause) for clause in matrix_clauses),
    )
    if reorder > 0:
        matrix_clauses = _mreorder(matrix_clauses, reorder)
        _trace("clausification.reorder", rounds=reorder)

    matrix = _build_matrix(
        matrix_clauses,
        mark_conjecture_clauses=mark_conjecture_clauses,
        collect_free_variables=True,
    )
    _trace(
        "clausification.done",
        clauses=len(matrix.clauses),
        literals=sum(len(clause) for clause in matrix.clauses),
    )
    return matrix


def make_nonclassical_matrix_from_formula(
    formula: Formula,
    *,
    translation: ClausificationTranslationMode = "default",
    reorder: int = 0,
    mark_conjecture_clauses: bool = False,
    logic: str,
) -> Matrix:
    normalized_logic = normalize_logic(logic)
    if (
        normalized_logic not in INTUITIONISTIC_LOGICS
        and normalized_logic not in MODAL_LOGICS
    ):
        raise NotImplementedError(
            f"connections non-classical matrix construction does not support {logic!r}."
        )
    if normalized_logic in INTUITIONISTIC_LOGICS and contains_modal_formula(formula):
        raise NotImplementedError(
            "intuitionistic matrix construction rejects modal formulas."
        )

    _trace(
        "clausification.nonclassical.formula.start",
        translation=translation,
        reorder=reorder,
        logic=logic,
    )
    with_equality = add_equality_axioms(formula)
    _trace(
        "clausification.equality_axioms",
        added=with_equality is not formula,
    )
    formula = univar(with_equality)
    _trace("clausification.univar")

    if translation == "nodef":
        nnf, _ = prefixed_def_nnf(formula, logic=logic, mode="nnf")
        _trace("clausification.def_nnf", mode="nnf")
        dnf_expr = _prefixed_dnf(nnf)
        _trace("clausification.dnf")
    elif translation != "def" and isinstance(formula, Impl):
        nnf_left, next_index = prefixed_def_nnf(
            formula.left,
            logic=logic,
            mode="nnf",
            polarity=False,
        )
        _trace("clausification.def_nnf", mode="nnf", side="left")
        dnf_left = _prefixed_dnf(nnf_left)
        _trace("clausification.dnf", side="left")
        dnf_right, _ = prefixed_def_nnf(
            formula.right,
            logic=logic,
            mode="def",
            start_index=next_index,
        )
        _trace("clausification.def_nnf", mode="def", side="right")
        dnf_expr = Or(_prefixed_dnf(dnf_right), dnf_left)
    else:
        nnf_expr, _ = prefixed_def_nnf(formula, logic=logic, mode="def")
        _trace("clausification.def_nnf", mode="def")
        dnf_expr = _prefixed_dnf(nnf_expr)
        _trace("clausification.dnf")

    matrix_clauses = _prefixed_mat(dnf_expr)
    _trace(
        "clausification.mat",
        clauses=len(matrix_clauses),
        literals=sum(len(clause) for clause in matrix_clauses),
    )
    if reorder > 0:
        matrix_clauses = _mreorder(matrix_clauses, reorder)
        _trace("clausification.reorder", rounds=reorder)

    matrix = _build_matrix(
        matrix_clauses,
        mark_conjecture_clauses=mark_conjecture_clauses,
        collect_free_variables=False,
    )
    _trace(
        "clausification.done",
        clauses=len(matrix.clauses),
        literals=sum(len(clause) for clause in matrix.clauses),
    )
    return matrix


def _build_matrix(
    matrix_clauses: list[list[Literal]],
    *,
    mark_conjecture_clauses: bool,
    collect_free_variables: bool,
) -> Matrix:
    clauses: list[Clause] = []
    for clause in matrix_clauses:
        if mark_conjecture_clauses:
            normalized = _strip_conjecture_marker(
                clause,
                collect_free_variables=collect_free_variables,
            )
            if normalized is not None:
                clauses.append(normalized)
            continue
        literals = tuple(clause)
        free_variables = (
            _free_variables_for_literals(literals) if collect_free_variables else ()
        )
        clauses.append(
            Clause(literals, free_variables=free_variables)
        )
    return Matrix(tuple(clauses))


def _cnf_clause_role(role: str) -> ClauseRole:
    return "conjecture" if role.lower() in _CONJECTURE_CNF_ROLES else "axiom"


def _strip_conjecture_marker(
    clause: list[Literal],
    *,
    collect_free_variables: bool,
) -> Clause | None:
    role: ClauseRole = "axiom"
    literals: list[Literal] = []
    saw_marker = False

    for literal in clause:
        if literal.atom.symbol == "#":
            saw_marker = True
            if literal.polarity:
                role = "conjecture"
            continue
        literals.append(literal)

    if not literals and saw_marker:
        return None
    literal_tuple = tuple(literals)
    free_variables = (
        _free_variables_for_literals(literal_tuple) if collect_free_variables else ()
    )
    return Clause(
        literal_tuple,
        role=role,
        free_variables=free_variables,
    )


def _trace(event: str, **payload: object) -> None:
    _ = payload
    if clausification_trace_logger.isEnabledFor(TRACE_LEVEL):
        trace(clausification_trace_logger, "%s", event)


def def_nnf(
    formula: Formula, start_index: int = 1, mode: str = "def"
) -> tuple[Formula, int]:
    nnf, defs, _, next_index = _def(formula, tuple(), mode, start_index)
    return _finalize_defs(defs, nnf), next_index


def prefixed_def_nnf(
    formula: Formula,
    *,
    logic: str,
    start_index: int = 1,
    mode: str = "def",
    polarity: bool = True,
) -> tuple[Formula, int]:
    normalized_logic = normalize_logic(logic)
    nnf, defs, _, next_index = _prefixed_def(
        formula,
        prefix_parts=(),
        free_vars=(),
        polarity=polarity,
        logic=normalized_logic,
        mode=mode,
        index=start_index,
    )
    return _finalize_prefixed_defs(defs, nnf), next_index


def _prefixed_def(
    formula: Formula,
    *,
    prefix_parts: tuple[Term, ...],
    free_vars: tuple[Variable, ...],
    polarity: bool,
    logic: str,
    mode: str,
    index: int,
) -> tuple[Formula, list[And], int, int]:
    if isinstance(formula, Atom | Eq):
        return _prefixed_literal(formula, Prefix(prefix_parts), polarity), [], 1, index

    if isinstance(formula, Not):
        next_prefix_parts = prefix_parts
        next_free_vars = free_vars
        next_index = index
        if logic in INTUITIONISTIC_LOGICS:
            prefix_part, next_index = (
                (
                    _skolem_prefix_part(index, free_vars),
                    index + 1,
                )
                if polarity
                else (_fresh_prefix_variable(index), index + 1)
            )
            next_prefix_parts = (*prefix_parts, prefix_part)
            if not polarity and isinstance(prefix_part, Variable):
                next_free_vars = (prefix_part, *free_vars)
        return _prefixed_def(
            formula.formula,
            prefix_parts=next_prefix_parts,
            free_vars=next_free_vars,
            polarity=not polarity,
            logic=logic,
            mode=mode,
            index=next_index,
        )

    if isinstance(formula, Box):
        if logic not in MODAL_LOGICS:
            raise NotImplementedError(
                "Box is supported only for modal matrix construction."
            )
        prefix_part, next_index = (
            (_skolem_prefix_part(index, free_vars, index_term=formula.index), index + 1)
            if polarity
            else (_fresh_prefix_variable(index), index + 1)
        )
        next_free_vars = (
            (prefix_part, *free_vars)
            if isinstance(prefix_part, Variable)
            else free_vars
        )
        return _prefixed_def(
            formula.body,
            prefix_parts=(*prefix_parts, prefix_part),
            free_vars=next_free_vars,
            polarity=polarity,
            logic=logic,
            mode=mode,
            index=next_index,
        )

    if isinstance(formula, Diamond):
        if logic not in MODAL_LOGICS:
            raise NotImplementedError(
                "Diamond is supported only for modal matrix construction."
            )
        prefix_part, next_index = (
            (_fresh_prefix_variable(index), index + 1)
            if polarity
            else (
                _skolem_prefix_part(index, free_vars, index_term=formula.index),
                index + 1,
            )
        )
        next_free_vars = (
            (prefix_part, *free_vars)
            if isinstance(prefix_part, Variable)
            else free_vars
        )
        return _prefixed_def(
            formula.body,
            prefix_parts=(*prefix_parts, prefix_part),
            free_vars=next_free_vars,
            polarity=polarity,
            logic=logic,
            mode=mode,
            index=next_index,
        )

    if isinstance(formula, Exists):
        if polarity:
            variable = _prefixed_variable(formula.variable, Prefix(prefix_parts))
            body = substitute_variable(formula.body, formula.variable.symbol, variable)
            return _prefixed_def(
                body,
                prefix_parts=prefix_parts,
                free_vars=(variable, *free_vars),
                polarity=True,
                logic=logic,
                mode=mode,
                index=index,
            )
        next_prefix_parts = prefix_parts
        next_free_vars = free_vars
        next_index = index + 1 if logic in INTUITIONISTIC_LOGICS else index
        skolem = _skolem_term(next_index, next_free_vars, Prefix(next_prefix_parts))
        body = substitute_variable(formula.body, formula.variable.symbol, skolem)
        return _prefixed_def(
            body,
            prefix_parts=next_prefix_parts,
            free_vars=next_free_vars,
            polarity=False,
            logic=logic,
            mode=mode,
            index=next_index + 1,
        )

    if isinstance(formula, Forall):
        if not polarity:
            next_prefix_parts = prefix_parts
            next_free_vars = free_vars
            next_index = index
            if logic in INTUITIONISTIC_LOGICS:
                prefix_part = _fresh_prefix_variable(index)
                next_index += 1
                next_prefix_parts = (*prefix_parts, prefix_part)
                next_free_vars = (prefix_part, *free_vars)
            variable = _prefixed_variable(formula.variable, Prefix(next_prefix_parts))
            body = substitute_variable(formula.body, formula.variable.symbol, variable)
            return _prefixed_def(
                body,
                prefix_parts=next_prefix_parts,
                free_vars=(variable, *next_free_vars),
                polarity=False,
                logic=logic,
                mode=mode,
                index=next_index,
            )

        next_prefix_parts = prefix_parts
        if logic in INTUITIONISTIC_LOGICS:
            prefix_part = _skolem_prefix_part(index, free_vars)
            next_prefix_parts = (*prefix_parts, prefix_part)
        skolem = _skolem_term(index, free_vars, Prefix(next_prefix_parts))
        body = substitute_variable(formula.body, formula.variable.symbol, skolem)
        return _prefixed_def(
            body,
            prefix_parts=next_prefix_parts,
            free_vars=free_vars,
            polarity=True,
            logic=logic,
            mode=mode,
            index=index + 1,
        )

    if isinstance(formula, Or):
        if polarity:
            left, defs_left, paths_left, next_index = _prefixed_def(
                formula.left,
                prefix_parts=prefix_parts,
                free_vars=free_vars,
                polarity=True,
                logic=logic,
                mode=mode,
                index=index,
            )
            right, defs_right, paths_right, final_index = _prefixed_def(
                formula.right,
                prefix_parts=prefix_parts,
                free_vars=free_vars,
                polarity=True,
                logic=logic,
                mode=mode,
                index=next_index,
            )
            if paths_left > paths_right:
                nnf = Or(right, left)
            else:
                nnf = Or(left, right)
            return nnf, defs_left + defs_right, paths_left * paths_right, final_index
        return _prefixed_binary(
            formula.left,
            formula.right,
            prefix_parts=prefix_parts,
            free_vars=free_vars,
            polarity=False,
            logic=logic,
            mode=mode,
            index=index,
        )

    if isinstance(formula, And):
        if polarity:
            return _prefixed_binary(
                formula.left,
                formula.right,
                prefix_parts=prefix_parts,
                free_vars=free_vars,
                polarity=True,
                logic=logic,
                mode=mode,
                index=index,
            )
        left, defs_left, paths_left, next_index = _prefixed_def(
            formula.left,
            prefix_parts=prefix_parts,
            free_vars=free_vars,
            polarity=False,
            logic=logic,
            mode=mode,
            index=index,
        )
        right, defs_right, paths_right, final_index = _prefixed_def(
            formula.right,
            prefix_parts=prefix_parts,
            free_vars=free_vars,
            polarity=False,
            logic=logic,
            mode=mode,
            index=next_index,
        )
        if paths_left > paths_right:
            nnf = Or(right, left)
        else:
            nnf = Or(left, right)
        return nnf, defs_left + defs_right, paths_left * paths_right, final_index

    if isinstance(formula, Impl):
        next_prefix_parts = prefix_parts
        next_free_vars = free_vars
        next_index = index
        if logic in INTUITIONISTIC_LOGICS:
            prefix_part, next_index = (
                (
                    _skolem_prefix_part(index, free_vars),
                    index + 1,
                )
                if polarity
                else (_fresh_prefix_variable(index), index + 1)
            )
            next_prefix_parts = (*prefix_parts, prefix_part)
            if not polarity and isinstance(prefix_part, Variable):
                next_free_vars = (prefix_part, *free_vars)
        if polarity:
            left, defs_left, paths_left, left_index = _prefixed_def(
                formula.left,
                prefix_parts=next_prefix_parts,
                free_vars=next_free_vars,
                polarity=False,
                logic=logic,
                mode=mode,
                index=next_index,
            )
            right, defs_right, paths_right, final_index = _prefixed_def(
                formula.right,
                prefix_parts=next_prefix_parts,
                free_vars=next_free_vars,
                polarity=True,
                logic=logic,
                mode=mode,
                index=left_index,
            )
            if paths_left > paths_right:
                nnf = Or(right, left)
            else:
                nnf = Or(left, right)
            return nnf, defs_left + defs_right, paths_left * paths_right, final_index
        return _prefixed_binary(
            formula.left,
            formula.right,
            prefix_parts=next_prefix_parts,
            free_vars=next_free_vars,
            polarity=True,
            logic=logic,
            mode=mode,
            index=next_index,
            right_polarity=False,
        )

    if isinstance(formula, Iff):
        expanded: Formula
        expanded = And(
            Impl(formula.left, formula.right),
            Impl(formula.right, formula.left),
        )
        return _prefixed_def(
            expanded,
            prefix_parts=prefix_parts,
            free_vars=free_vars,
            polarity=polarity,
            logic=logic,
            mode=mode,
            index=index,
        )

    raise TypeError(f"Unsupported formula node: {type(formula)!r}")


def _prefixed_binary(
    left_formula: Formula,
    right_formula: Formula,
    *,
    prefix_parts: tuple[Term, ...],
    free_vars: tuple[Variable, ...],
    polarity: bool,
    logic: str,
    mode: str,
    index: int,
    right_polarity: bool | None = None,
) -> tuple[Formula, list[And], int, int]:
    left, defs_left, paths_left, next_index = _prefixed_def(
        left_formula,
        prefix_parts=prefix_parts,
        free_vars=free_vars,
        polarity=polarity,
        logic=logic,
        mode=mode,
        index=index,
    )
    left, defs_left, next_index = _define_prefixed_or(
        left,
        defs_left,
        free_vars,
        next_index,
        mode,
    )
    right, defs_right, paths_right, final_index = _prefixed_def(
        right_formula,
        prefix_parts=prefix_parts,
        free_vars=free_vars,
        polarity=polarity if right_polarity is None else right_polarity,
        logic=logic,
        mode=mode,
        index=next_index,
    )
    right, defs_right, final_index = _define_prefixed_or(
        right,
        defs_right,
        free_vars,
        final_index,
        mode,
    )
    if paths_left > paths_right:
        nnf = And(right, left)
    else:
        nnf = And(left, right)
    return nnf, defs_left + defs_right, paths_left + paths_right, final_index


def _define_prefixed_or(
    expr: Formula,
    definitions: list[And],
    free_vars: tuple[Variable, ...],
    index: int,
    mode: str,
) -> tuple[Formula, list[And], int]:
    if not isinstance(expr, Or) or mode != "def":
        return expr, definitions, index
    predicate = _def_predicate(index, free_vars)
    definition_literal = _prefixed_literal(predicate, Prefix(()), polarity=True)
    negated_definition_literal = _prefixed_literal(
        predicate,
        Prefix(()),
        polarity=False,
    )
    definition = And(negated_definition_literal, expr)
    return definition_literal, [definition, *definitions], index + 1


def _def(
    formula: Formula,
    free_vars: tuple[Variable, ...],
    mode: str,
    index: int,
) -> tuple[Formula, list[Formula], int, int]:
    while True:
        rewritten = _rewrite_logical_connectives(formula, mode)
        if rewritten is formula:
            break
        formula = rewritten

    if isinstance(formula, Exists):
        return _def(formula.body, (formula.variable,) + free_vars, mode, index)

    if isinstance(formula, Forall):
        skolem_term = _make_skolem_term(index, free_vars)
        body = substitute_variable(formula.body, formula.variable.symbol, skolem_term)
        return _def(body, free_vars, mode, index + 1)

    if isinstance(formula, Or):
        left, defs_left, paths_left, next_index = _def(
            formula.left, free_vars, mode, index
        )
        right, defs_right, paths_right, final_index = _def(
            formula.right, free_vars, mode, next_index
        )
        if paths_left > paths_right:
            nnf = Or(right, left)
        else:
            nnf = Or(left, right)
        return nnf, defs_left + defs_right, paths_left * paths_right, final_index

    if isinstance(formula, And):
        left, defs_left_raw, paths_left, next_index = _def(
            formula.left, free_vars, mode, index
        )
        defs_left = list(defs_left_raw)
        left_index = next_index
        if isinstance(left, Or) and mode == "def":
            pred = _def_predicate(left_index, free_vars)
            defs_left = [And(Not(pred), left), *defs_left]
            left = pred
            left_index += 1

        right, defs_right_raw, paths_right, final_index = _def(
            formula.right, free_vars, mode, left_index
        )
        defs_right = list(defs_right_raw)
        right_index = final_index
        if isinstance(right, Or) and mode == "def":
            pred = _def_predicate(right_index, free_vars)
            defs_right = [And(Not(pred), right), *defs_right]
            right = pred
            right_index += 1

        if paths_left > paths_right:
            nnf = And(right, left)
        else:
            nnf = And(left, right)
        return nnf, defs_left + defs_right, paths_left + paths_right, right_index

    if _is_literal(formula):
        return formula, [], 1, index
    raise ValueError(f"Expected literal in def_nnf, got {formula!r}")


def _rewrite_logical_connectives(formula: Formula, mode: str) -> Formula:
    if isinstance(formula, Not) and isinstance(formula.formula, Not):
        return formula.formula.formula
    if isinstance(formula, Not) and isinstance(formula.formula, Forall):
        inner = formula.formula
        return Exists(inner.variable, Not(inner.body))
    if isinstance(formula, Not) and isinstance(formula.formula, Exists):
        inner = formula.formula
        return Forall(inner.variable, Not(inner.body))
    if isinstance(formula, Not) and isinstance(formula.formula, Or):
        inner = formula.formula
        return And(Not(inner.left), Not(inner.right))
    if isinstance(formula, Not) and isinstance(formula.formula, And):
        inner = formula.formula
        return Or(Not(inner.left), Not(inner.right))
    if isinstance(formula, Impl):
        return Or(Not(formula.left), formula.right)
    if isinstance(formula, Not) and isinstance(formula.formula, Impl):
        inner = formula.formula
        return And(inner.left, Not(inner.right))
    if isinstance(formula, Iff):
        if mode == "def":
            return And(
                Impl(formula.left, formula.right), Impl(formula.right, formula.left)
            )
        return Or(
            And(formula.left, formula.right),
            And(Not(formula.left), Not(formula.right)),
        )
    if isinstance(formula, Not) and isinstance(formula.formula, Iff):
        inner = formula.formula
        return Or(And(inner.left, Not(inner.right)), And(Not(inner.left), inner.right))
    return formula


def _make_skolem_term(index: int, free_vars: tuple[Variable, ...]) -> Term:
    args: tuple[Term, ...] = (Function(str(index)), *free_vars)
    return Function("f_skolem", args)


def _skolem_term(
    index: int,
    free_vars: tuple[Variable, ...],
    prefix: Prefix,
) -> Function:
    args: tuple[Term, ...] = (Function(str(index)), *free_vars)
    return Function("f_skolem", args, prefix=prefix)


def _skolem_prefix_part(
    index: int,
    free_vars: tuple[Variable, ...],
    *,
    index_term: Term | None = None,
) -> Function:
    args: tuple[Term, ...]
    if index_term is None:
        args = (Function(str(index)), *free_vars)
    else:
        args = (index_term, Function(str(index)), *free_vars)
    return Function("c_skolem", args)


def _fresh_prefix_variable(index: int) -> Variable:
    return Variable(f"PV{index}")


def _prefixed_variable(variable: Variable, prefix: Prefix) -> Variable:
    return Variable(variable.symbol, prefix=prefix, vid=variable.vid)


def _def_predicate(index: int, free_vars: tuple[Variable, ...]) -> Atom:
    return Atom("p_defini", (Function(str(index)), *free_vars))


def _prefixed_literal(formula: Atom | Eq, prefix: Prefix, polarity: bool) -> Prefixed:
    return Prefixed(formula if polarity else Not(formula), prefix)


def _finalize_defs(definitions: list[Formula], nnf: Formula) -> Formula:
    pending = list(definitions)
    result = nnf
    while pending:
        current = pending.pop(0)
        if isinstance(current, And) and isinstance(current.right, Or):
            pending.insert(0, And(current.left, current.right.left))
            pending.insert(1, And(current.left, current.right.right))
            continue
        result = Or(current, result)
    return result


def _finalize_prefixed_defs(
    definitions: list[And],
    nnf: Formula,
) -> Formula:
    pending = list(definitions)
    result = nnf
    while pending:
        current = pending.pop(0)
        if isinstance(current.right, Or):
            pending.insert(0, And(current.left, current.right.left))
            pending.insert(1, And(current.left, current.right.right))
            continue
        result = Or(current, result)
    return result


def _mreorder(matrix: list[list[Literal]], rounds: int) -> list[list[Literal]]:
    return mreorder_items(matrix, rounds)
