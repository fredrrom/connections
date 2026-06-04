from __future__ import annotations

from dataclasses import dataclass
from lark import Transformer, Tree, v_args

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
    Impl,
    Iff,
    Not,
    Or,
    Term,
    Variable,
)


@dataclass(frozen=True)
class IncludeOptionals:
    formula_selection: tuple[str, ...] | str | None = None
    space_name: str | None = None


@dataclass(frozen=True)
class StmtFOF:
    name: str
    role: str
    formula: Formula
    annotations: object | None = None


@dataclass(frozen=True)
class StmtCNF:
    name: str
    role: str
    formula: Formula
    annotations: object | None = None


@dataclass(frozen=True)
class StmtQMF:
    name: str
    role: str
    formula: Formula
    annotations: object | None = None


@dataclass(frozen=True)
class StmtInclude:
    file_name: str
    selection: tuple[str, ...] | str | None = None
    space_name: str | None = None


StmtFormula = StmtFOF | StmtCNF | StmtQMF
Stmt = StmtFormula | StmtInclude


@dataclass(frozen=True)
class TptpFile:
    items: list[Stmt]


@v_args(inline=True)
class TptpToIRTransformer(Transformer):
    def __default_token__(self, token):
        return str(token)

    def __default__(self, data, children, meta):
        return Tree(data, children)

    def SINGLE_QUOTED(self, token):
        value = str(token)
        return value[1:-1].replace("\\'", "'").replace("\\\\", "\\")

    def DISTINCT_OBJECT(self, token):
        value = str(token)
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")

    def tptp_file(self, *items):
        return TptpFile(
            items=[
                item
                for item in items
                if isinstance(item, (StmtFOF, StmtCNF, StmtQMF, StmtInclude))
            ]
        )

    def fof_annotated(self, name, role, formula, annotations=None):
        return StmtFOF(name=name, role=role, formula=formula, annotations=annotations)

    def cnf_annotated(self, name, role, formula, annotations=None):
        return StmtCNF(name=name, role=role, formula=formula, annotations=annotations)

    def qmf_annotated(self, name, role, formula, annotations=None):
        return StmtQMF(name=name, role=role, formula=formula, annotations=annotations)

    def include(self, file_name, optionals=None):
        if isinstance(optionals, IncludeOptionals):
            return StmtInclude(
                file_name=file_name,
                selection=optionals.formula_selection,
                space_name=optionals.space_name,
            )
        return StmtInclude(file_name=file_name)

    def include_optionals(self, formula_selection=None, space_name=None):
        return IncludeOptionals(
            formula_selection=formula_selection, space_name=space_name
        )

    def star(self, _star):
        return "*"

    def name_list(self, *names):
        return tuple(names)

    def formula_role(self, role, _detail=None):
        return role

    def annotations(self, source=None, optional_info=None):
        if source is None:
            return None
        return (source, optional_info)

    def fof_binary_nonassoc(self, left, operator, right):
        if operator == "<=>":
            return Iff(left, right)
        if operator == "=>":
            return Impl(left, right)
        if operator == "<=":
            return Impl(right, left)
        if operator == "<~>":
            return Not(Iff(left, right))
        if operator == "~|":
            return Not(Or(left, right))
        if operator == "~&":
            return Not(And(left, right))
        raise ValueError(f"Unsupported binary operator: {operator!r}")

    def fof_or_formula(self, left, right):
        return Or(left, right)

    def fof_and_formula(self, left, right):
        return And(left, right)

    def cnf_or_formula(self, left, right):
        return Or(left, right)

    def fof_prefix_unary(self, operator, arg):
        if operator != "~":
            raise ValueError(f"Unsupported unary prefix operator: {operator!r}")
        return Not(arg)

    def cnf_prefix_unary(self, operator, arg):
        if operator != "~":
            raise ValueError(f"Unsupported CNF unary operator: {operator!r}")
        return Not(arg)

    def fof_infix_unary(self, left, operator, right):
        if operator != "!=":
            raise ValueError(f"Unsupported unary infix operator: {operator!r}")
        return Not(Eq(left, right))

    def cnf_infix_unary(self, left, operator, right):
        if operator != "!=":
            raise ValueError(f"Unsupported CNF infix operator: {operator!r}")
        return Not(Eq(left, right))

    def modal_connective(self, operator, index=None):
        return str(operator), index

    def fof_modal_unary(self, connective, body):
        operator, index = connective
        if operator == "#box":
            return Box(body=body, index=index)
        if operator == "#dia":
            return Diamond(body=body, index=index)
        raise ValueError(f"Unsupported modal operator: {operator!r}")

    def fof_quantified_formula(self, quantifier, variables, body):
        result = body
        for variable in reversed(variables):
            if quantifier == "!":
                result = Forall(variable, result)
            elif quantifier == "?":
                result = Exists(variable, result)
            else:
                raise ValueError(f"Unsupported quantifier: {quantifier!r}")
        return result

    def fof_variable_list(self, first, rest=None):
        if rest is None:
            return (first,)
        return (first, *rest)

    def term_tuple(self, symbol, args=None) -> tuple[str, tuple[Term, ...]]:
        if args is None:
            return str(symbol), tuple()
        return str(symbol), tuple(args)

    def fof_atomic_formula(self, part):
        if isinstance(part, tuple) and len(part) == 2:
            symbol, args = part
            if not args and symbol == "$true":
                truth = Atom("true___")
                return Impl(truth, truth)
            if not args and symbol == "$false":
                falsehood = Atom("false___")
                return And(falsehood, Not(falsehood))
            return Atom(symbol, args)
        if isinstance(part, Formula):
            return part
        raise TypeError(f"Expected (symbol,args) tuple or formula, got: {part!r}")

    def fof_function_term(self, part):
        if isinstance(part, tuple) and len(part) == 2:
            symbol, args = part
            return Function(symbol, args)
        raise TypeError(f"Expected (symbol,args) tuple, got: {part!r}")

    def fof_defined_infix_formula(self, left, operator, right):
        if operator != "=":
            raise ValueError(f"Unsupported defined infix operator: {operator!r}")
        return Eq(left, right)

    def fof_arguments(self, *terms):
        return tuple(terms)

    def variable(self, name):
        return Variable(name)
