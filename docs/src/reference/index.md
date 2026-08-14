# API reference

Generated from docstrings. If something here is wrong or missing, fix the
docstring rather than this page.

These pages describe the code **as it is today**. The
[design notes](../design/architecture.md) describe the target, and where the two
disagree the notes are the intent.

| | |
|---|---|
| [syntax](syntax.md) | terms, literals, clauses, matrices |
| [parsing](parsing.md) | TPTP text to statements and formulas |
| [clausification](clausification.md) | formulas to a matrix |
| [constraints](constraints.md) | unification, substitutions, prefixes |
| [policy](policy.md) | the policy interface and shipped policies |

!!! note "Not yet covered"

    The calculus and run surfaces are mid-restructure -- `prover` splits into
    `calculus` and `run`. Reference pages for them land after that move, rather
    than documenting module paths that are about to change.
