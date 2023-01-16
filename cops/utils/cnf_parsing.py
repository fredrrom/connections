import re

from cops.utils.primitives import *


def file2cnf(path):
    with open(path, "r") as file:
        return parse_fof(file.read())


def parse_fof(fof):
    clauses_str = re.findall(r"\[.*\]", fof)[0][2:-2].split(r"],[")#re.findall(r"\[.*\]", fof)[0][2:-2].split(r"], [")
    if clauses_str == ['']:
        return Matrix([])
    return Matrix([parse_clause(clause_str) for clause_str in clauses_str])


def parse_clause(clause_str):
    literals = []
    for literal_str in split_bracket(clause_str):
        lit = parse_literal(literal_str)
        literals.append(lit)
    return literals


def parse_literal(literal_str):
    neg = False
    if literal_str[0] == "-":
        neg = True
        literal_str = literal_str[1:]#literal_str[2:-1]
    split = literal_str.split(r"(", 1)
    terms = []
    if len(split) > 1:
        terms_str = split[1][:-1]
        for term_str in split_bracket(terms_str):
            terms.append(parse_term(term_str))
    literal = Literal(split[0], tuple(terms), neg=neg)
    return literal


def parse_term(term_str):
    split = term_str.split(r"(", 1)
    term_name = split[0]
    if term_name[0] == "_":
        return Variable(term_name)
    elif term_name.isnumeric():
        return Constant(term_name)
    subterms = []
    if len(split) > 1:
        subterms_str = split[1][:-1]
        for subterm_str in split_bracket(subterms_str):
            subterms.append(parse_term(subterm_str))
    return Function(term_name, tuple(subterms))


def split_bracket(str):
    strs = []
    num_bracket = 0
    split_indeces = [0]
    for i, c in enumerate(str):
        if c == "(":
            num_bracket += 1
        elif c == ")":
            num_bracket -= 1
        elif num_bracket == 0 and c == ",":
            split_indeces.append(i)
    split_indeces.append(len(str))
    for i in range(len(split_indeces) - 1):
        start = split_indeces[i]
        end = split_indeces[i + 1]
        if str[start] == ",":
            strs.append(str[start + 1: end])#strs.append(str[start + 2: end])
        else:
            strs.append(str[start:end])
    return strs
