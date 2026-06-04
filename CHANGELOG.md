# Changelog

## 0.1.0 - Unreleased

Initial prover-core release.

### Added

- Concrete `Prover` loop with direct problem-path arguments, strategy-owned
  policy construction, and hooks.
- Public action records under `connections.prover.actions`.
- DFS, iterative-deepening, and pycop policy/strategy components.
- Transactional term, prefix, and free-variable constraint stores.
- Native TPTP parsing for `fof`, `cnf`, `qmf`, and `include`.
- Native matrix construction for the 0.1 classical FOF/CNF slice and an
  initial prefix-annotated non-classical slice.
- `pycop` CLI with settings, schedules, source directories, trace output, and
  budget options.
- Developer tools for corpus runs, profiling, and leanCoP-family parity checks.
- MkDocs documentation under `docs/`.

### Public Boundary

The main API is:

```python
from connections.prover import Prover
from connections.pycop.strategy import PycopStrategy

result = Prover().run("problem.p", strategy=PycopStrategy())
```

Strategies construct fresh policies. Policies choose among legal actions
provided by `Dynamics`. Hooks observe choices, transitions, proof discovery,
and strategy completion.

Use this changelog section as the GitHub release body for `0.1.0`.
