from lark import Lark, Transformer

from connections.logic.syntax import Clause, Literal, Matrix
from connections.utils.factories import (
    intern_constant,
    intern_function,
    intern_literal,
    intern_variable,
)


_GRAMMAR = r"""
?start: cnf_file

cnf_file: "cnf" "(" CNF_PREAMBLE? clause_list ")" "."?

clause_list: "[" clause ("," clause)* "]"
clause: "[" literal ("," literal)* "]"

literal: negated | atom
negated: "-" "(" atom ")" | "-" atom
atom: NAME ["(" term_list ")"]

term_list: term ("," term)*
?term: variable
     | constant
     | function
     | NAME    -> bare_name

variable: VAR
constant: NUM | STRING
function: NAME "(" term_list ")"

CNF_PREAMBLE: /[^[]+/

NAME: /[A-Za-z][A-Za-z0-9_+]*/
VAR: /_[A-Za-z0-9_]*/
NUM: /[0-9]+/
STRING: /'[^']*'/

%import common.WS
%ignore WS
%ignore /%[^\n]*/
"""


class _CnfToAst(Transformer):
    def cnf_file(self, items):
        return Matrix(items[-1])

    def clause_list(self, items):
        return tuple(items)

    def clause(self, items):
        return Clause(tuple(items))

    def literal(self, items):
        return items[0]

    def atom(self, items):
        name = str(items[0])
        if len(items) == 1:
            return intern_literal(name, args=(), neg=False)
        return intern_literal(name, args=tuple(items[1]), neg=False)

    def negated(self, items):
        lit = items[-1]
        return intern_literal(lit.name, args=lit.args, prefix=lit.prefix, neg=True)

    def term_list(self, items):
        return tuple(items)

    def function(self, items):
        name = str(items[0])
        return intern_function(name, args=tuple(items[1]))

    def variable(self, items):
        return intern_variable(str(items[0]), vid=0)

    def constant(self, items):
        token = str(items[0])
        if token.startswith("'") and token.endswith("'"):
            token = token[1:-1]
        return intern_constant(token)

    def bare_name(self, items):
        token = str(items[0])
        return intern_constant(token)


_PARSER = Lark(_GRAMMAR, start="start", parser="lalr")


def file2cnf(path):
    with open(path, "r") as file:
        return parse_fof(file.read())


def parse_fof(fof):
    tree = _PARSER.parse(fof)
    return _CnfToAst().transform(tree)
