from abc import ABC
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union


class Expression(ABC):
    """Base class for all logical expressions.

    Attributes:
        symbol: The symbol/name of the expression.
        args: List of arguments to the expression.
        prefix: Optional prefix for modal/intuitionistic logic.
    """

    def __init__(
        self, symbol: str, args: List[Any] = None, prefix: Optional[Any] = None
    ) -> None:
        """Initialize an expression.

        Args:
            symbol: The symbol/name of the expression.
            args: List of arguments to the expression.
            prefix: Optional prefix for modal/intuitionistic logic.
        """
        self.symbol = symbol
        self.args = args or []
        self.prefix = prefix

    def __repr__(self) -> str:
        """Return a string representation of the expression.

        Returns:
            A string in the format 'symbol(arg1, arg2, ...)'.
        """
        arg_str = "(" + ", ".join(str(x) for x in self.args) + ")" if self.args else ""
        return f"{self.symbol}{arg_str}"

    def __eq__(self, other: Any) -> bool:
        """Check if two expressions are equal.

        Args:
            other: The other expression to compare with.

        Returns:
            True if the expressions have the same symbol and arguments.
        """
        if not isinstance(other, Expression):
            return False
        return self.symbol == other.symbol and self.args == other.args

    def __hash__(self) -> int:
        """Compute a hash value for the expression.

        Returns:
            A hash value based on the symbol and arguments.
        """
        return hash((self.symbol, tuple(self.args)))


class Term(Expression):
    """Base class for logical terms (variables, constants, functions)."""

    def copy(self, num: int) -> "Term":
        """Create a copy of the term with a new copy number.

        Args:
            num: The new copy number.

        Returns:
            A new copy of the term.
        """
        return type(self)(
            self.symbol,
            [arg.copy(num) for arg in self.args],
            None if self.prefix is None else self.prefix.copy(num),
        )


class Variable(Term):
    """Represents a logical variable.

    Variables can have a copy number to distinguish between different
    instances of the same variable.
    """
    def __init__(
        self, symbol: str, args: List[Any] = None, prefix: Optional[Any] = None
    ) -> None:
        """Initialize a variable.

        Args:
            symbol: The variable name.
            args: List of arguments (empty for variables).
            prefix: Optional prefix for modal/intuitionistic logic.
        """
        super().__init__(symbol, args, prefix)
        self.copy_num = 0

    def __repr__(self) -> str:
        """Return a string representation of the variable.

        Returns:
            A string in the format 'symbol[copy_num]' if copy_num is non-zero.
        """
        if Variable.show_copy_num and self.copy_num != 0:
            copy_str = f"{self.copy_num}"
        else:
            copy_str = ""
        return super(Term, self).__repr__() + copy_str

    def __eq__(self, other: Any) -> bool:
        """Check if two variables are equal.

        Args:
            other: The other variable to compare with.

        Returns:
            True if the variables have the same symbol and copy number.
        """
        return super().__eq__(other) and self.copy_num == other.copy_num

    def __hash__(self) -> int:
        """Compute a hash value for the variable.

        Returns:
            A hash value based on the symbol and copy number.
        """
        return hash((self.symbol, self.copy_num))

    def copy(self, num: int) -> "Variable":
        """Create a copy of the variable with a new copy number.

        Args:
            num: The new copy number.

        Returns:
            A new copy of the variable.
        """
        copy = super().copy(num)
        copy.copy_num = num
        return copy


class Constant(Term):
    """Represents a logical constant."""

    pass


class Function(Term):
    """Represents a logical function."""

    pass


class Literal(Expression):
    """Represents a logical literal (atom or negated atom).

    Attributes:
        neg: Whether the literal is negated.
        matrix_pos: Position of the literal in the matrix.
    """

    def __init__(
        self,
        symbol: str,
        args: List[Any] = None,
        prefix: Optional[Any] = None,
        neg: bool = False,
        matrix_pos: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Initialize a literal.

        Args:
            symbol: The predicate symbol.
            args: List of arguments to the predicate.
            prefix: Optional prefix for modal/intuitionistic logic.
            neg: Whether the literal is negated.
            matrix_pos: Position of the literal in the matrix.
        """
        super().__init__(symbol, args, prefix)
        self.neg = neg
        self.matrix_pos = matrix_pos

    def __repr__(self) -> str:
        """Return a string representation of the literal.

        Returns:
            A string in the format '-symbol(args)' for negated literals.
        """
        neg_str = "-" if self.neg else ""
        return neg_str + super().__repr__() 


class Matrix:
    """Represents a matrix of clauses in CNF format."""

    def __init__(self, clauses: List[List[Literal]]) -> None:
        """Initialize a matrix by indexing a list of clauses.

        Args:
            clauses: List of clauses, where each clause is a list of literals.
        """
        self.clauses = clauses
        self.complement = defaultdict(list)
        self.positive_clauses = []
        for i, clause in enumerate(self.clauses):
            positive = True
            for j, lit in enumerate(clause):
                lit.matrix_pos = (i, j)
                self.complement[(not lit.neg, lit.symbol)].append((i, j))
                if lit.neg:
                    positive = False
            if positive:
                self.positive_clauses.append(i)
