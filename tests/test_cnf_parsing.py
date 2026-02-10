from connections.utils.cnf_parsing import parse_fof
from connections.logic.syntax import (
    Clause,
    Constant,
    Function,
    Literal,
    Matrix,
    Variable,
)


def test_parse_cnf_syn081_exact_ast():
    with open("tests/cnf_problems/SYN081+1.cnf", "r") as file:
        parsed = parse_fof(file.read())

    expected = Matrix(
        (
            Clause(
                (
                    Literal("big_f", args=(Variable("_13444"),)),
                    Literal(
                        "big_f",
                        args=(Function("f", args=(Variable("_13444"),)),),
                        neg=True,
                    ),
                )
            ),
            Clause(
                (
                    Literal("big_f", args=(Variable("_13104"),)),
                    Literal(
                        "big_f",
                        args=(Function("f", args=(Variable("_13104"),)),),
                    ),
                )
            ),
            Clause(
                (
                    Literal("big_f", args=(Variable("_13104"),), neg=True),
                    Literal(
                        "big_f",
                        args=(Function("f", args=(Variable("_13104"),)),),
                        neg=True,
                    ),
                )
            ),
        )
    )

    assert parsed == expected


def test_parse_cnf_syn726_exact_ast():
    with open("tests/cnf_problems/SYN726+1.cnf", "r") as file:
        parsed = parse_fof(file.read())

    expected = Matrix(
        (
            Clause(
                (
                    Literal(
                        "q",
                        args=(
                            Function("f_skolem", args=(Constant("3"),)),
                            Function("f_skolem", args=(Constant("4"),)),
                        ),
                    ),
                )
            ),
            Clause(
                (
                    Literal(
                        "p",
                        args=(
                            Function("f_skolem", args=(Constant("1"),)),
                            Function("f_skolem", args=(Constant("2"),)),
                        ),
                    ),
                )
            ),
            Clause(
                (
                    Literal(
                        "p",
                        args=(Variable("_192"), Variable("_196")),
                        neg=True,
                    ),
                    Literal(
                        "p",
                        args=(Variable("_192"), Variable("_194")),
                    ),
                    Literal(
                        "p",
                        args=(Variable("_194"), Variable("_196")),
                    ),
                )
            ),
            Clause(
                (
                    Literal(
                        "q",
                        args=(Variable("_276"), Variable("_280")),
                        neg=True,
                    ),
                    Literal(
                        "q",
                        args=(Variable("_276"), Variable("_278")),
                    ),
                    Literal(
                        "q",
                        args=(Variable("_278"), Variable("_280")),
                    ),
                )
            ),
            Clause(
                (
                    Literal(
                        "q",
                        args=(Variable("_360"), Variable("_362")),
                    ),
                    Literal(
                        "q",
                        args=(Variable("_362"), Variable("_360")),
                        neg=True,
                    ),
                )
            ),
            Clause(
                (
                    Literal(
                        "p",
                        args=(Variable("_418"), Variable("_430")),
                        neg=True,
                    ),
                    Literal(
                        "q",
                        args=(Variable("_418"), Variable("_430")),
                        neg=True,
                    ),
                )
            ),
        )
    )

    assert parsed == expected
