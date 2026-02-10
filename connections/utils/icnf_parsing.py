import re

from connections.logic.syntax import (
    Clause,
    Constant,
    Function,
    Literal,
    Matrix,
    Prefix,
    Variable,
)


def file2cnf(path):
    with open(path, "r") as file:
        return parse_fof(file.read())


def parse_fof(fof):
    clauses_str = re.findall(r"\[.*\]", fof)[0][2:-2].split(r"],[")
    clauses = tuple(
        parse_clause(clause_str) for clause_str in clauses_str if clause_str
    )
    return Matrix(clauses)


def parse_clause(clause_str):
    literals = []
    for literal_str in split_bracket(clause_str):
        literals.append(parse_literal(literal_str))
    return Clause(tuple(literals))


def parse_literal(literal_str):
    neg = False
    if literal_str.startswith("-"):
        neg = True
        literal_str = literal_str[1:]
    lit = find_pre(literal_str)
    split = lit[0].split(r"(", 1)
    terms = []
    if len(split) > 1:
        terms_str = split[1][:-1]
        for term_str in split_bracket(terms_str):
            terms.append(parse_term(term_str))
    prefix = parse_prefix(lit[1]) if len(lit) > 1 else Prefix(())
    return Literal(split[0], args=tuple(terms), prefix=prefix, neg=neg)


def parse_prefix(prefix_src: str) -> Prefix:
    prefix_term = parse_term(f"string{prefix_src}")
    if isinstance(prefix_term, Prefix):
        return prefix_term
    if isinstance(prefix_term, Function) and prefix_term.name == "string":
        return Prefix(tuple(prefix_term.args))
    return Prefix((prefix_term,))


def parse_term(term_str):
    if term_str.isnumeric() or term_str[0] == "'":
        return Constant(term_str)
    term = find_pre(term_str)
    split = term[0].split(r"(", 1)
    term_name = split[0]
    if len(term) > 1 and (term_name == "f_skolem" or term_name[0] == "_"):
        prefixes = parse_prefix(term[1])
    else:
        prefixes = Prefix(())
        split = term_str.split(r"(", 1)
    if term_name == "string":
        parts = []
        if len(split) > 1:
            subterms_str = split[1][:-1]
            for subterm_str in split_bracket(subterms_str):
                parts.append(parse_term(subterm_str))
        return Prefix(tuple(parts))
    if term_name[0] == "_":
        return Variable(term_name, prefix=prefixes)
    subterms = []
    if len(split) > 1:
        subterms_str = split[1][:-1]
        for subterm_str in split_bracket(subterms_str):
            subterms.append(parse_term(subterm_str))
    return Function(term_name, args=tuple(subterms), prefix=prefixes)


def find_pre(text):
    num_bracket = 0
    for i, c in enumerate(text):
        if c == "(":
            num_bracket += 1
        elif c == ")":
            num_bracket -= 1
        elif num_bracket == 0 and c == ":":
            return [text[:i], text[i + 4 :]]
    return [text]


def split_bracket(text):
    parts = []
    num_bracket = 0
    split_indices = [0]
    for i, c in enumerate(text):
        if c == "(":
            num_bracket += 1
        elif c == ")":
            num_bracket -= 1
        elif num_bracket == 0 and c == ",":
            split_indices.append(i)
    split_indices.append(len(text))
    for i in range(len(split_indices) - 1):
        start = split_indices[i]
        end = split_indices[i + 1]
        if text[start] == ",":
            parts.append(text[start + 1 : end])
        else:
            parts.append(text[start:end])
    return parts
