from collections import defaultdict
from abc import ABC


class Expression(ABC):
    def __init__(self, symbol, args=[], prefix=None):
        self.symbol = symbol
        self.args = args
        self.prefix = prefix

    def __str__(self):
        arg_str = "(" + ", ".join(str(x) for x in self.args) + ")" if self.args else ''
        return str(self.symbol) + arg_str

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if len(self.args) != len(other.args):
            return False
        return self.symbol == other.symbol and all(
            arg1 == arg2 for (arg1, arg2) in zip(self.args, other.args)
        )

    def __hash__(self):
        return hash(self.symbol) ^ hash(tuple(self.args))


class Term(Expression):
    def copy(self, num):
        new_prefix = None
        if self.prefix is not None:
            new_prefix = self.prefix.copy(num)
        return type(self)(self.symbol,
                          [arg.copy(num) for arg in self.args],
                          new_prefix)


class Variable(Term):
    def copy(self, num):
        copy = super().copy(num)
        copy.symbol = f"{self.symbol}{num}"
        return copy


class Constant(Term):
    pass


class Function(Term):
    pass


class Literal(Expression):
    def __init__(self, symbol, args=[], prefix=None, neg=False, matrix_pos=None):
        super().__init__(symbol, args, prefix)
        self.neg = neg
        self.matrix_pos = matrix_pos

    def __str__(self):
        neg_str = '-' if self.neg else ''
        return neg_str + super().__str__()

    def copy(self, num):
        new_prefix = None
        if self.prefix is not None:
            new_prefix = self.prefix.copy(num)
        return Literal(
            self.symbol,
            [arg.copy(num) for arg in self.args],
            new_prefix,
            self.neg,
            self.matrix_pos
        )


class Matrix:
    def __init__(self, clauses):
        self.index = 0
        self.clauses = clauses
        self.num_clauses = len(clauses)
        self._update_mappings()

    def reset(self):
        """
        reset counter for creation of fresh variables
        """
        self.index = 0

    def _update_mappings(self):
        self.complement = defaultdict(list)
        self.flattened_idx = {}
        self.positive_clauses = []
        self.num_lits = sum([len(clause) for clause in self.clauses])
        lit_idx = 0
        for i, clause in enumerate(self.clauses):
            positive = True
            for j, lit in enumerate(clause):
                lit.matrix_pos = (i, j)
                self.flattened_idx[(i, j)] = lit_idx
                lit_idx += 1
                self.complement[(not lit.neg, lit.symbol)].append((i, j))
                if lit.neg:
                    positive = False
            if positive:
                self.positive_clauses.append(i)

    def complements(self, literal):
        """
        :param literal: literal to find complements for
        :return: list of matrix positions of complements
        """
        return self.complement[(literal.neg, literal.symbol)]

    def copy(self, clause_idx):
        """
        :param clause_idx: matrix index for the clause to copy
        :return: a copy of the clause at clause_idx
        """
        self.index += 1
        return [lit.copy(self.index) for lit in self.clauses[clause_idx]]

    def lit_idx(self, literal):
        """
        finds the index of the literal in the flattened matrix
        :param literal: literal to find the index of in the flattened matrix
        :return: index of the literal in the flattened matrix
        """
        return self.flattened_idx[literal.matrix_pos]
