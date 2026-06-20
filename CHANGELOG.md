# Changelog

## 0.1.0 - Unreleased

Initial prover-loop release.

### Added

- Concrete `Prover` loop with direct problem-path arguments and data-oriented
  strategies.
- Public action records under `connections.prover.actions`.
- Reusable `connections.runs` helpers for problem selection, corpus-run rows,
  summaries, and generic prover execution.
- DFS and iterative-deepening policy components with first-action default
  selection.
- Transactional term, prefix, and free-variable constraint stores.
- Native TPTP parsing for `fof`, `cnf`, `qmf`, and `include`.
- Native matrix construction for the 0.1 classical FOF/CNF slice and an
  initial prefix-annotated non-classical slice.
- `pycop` CLI with settings, schedules, source directories, trace output,
  corpus JSONL output, and budget options.
- `connections-download-benchmarks` CLI for benchmark setup.
- Developer tools for leanCoP-family parity checks.
- MkDocs documentation under `docs/`.

### Public Boundary

The main API is:

```python
from connections.prover import Prover
from connections.prover import ProblemSpec, StrategySchedule, make_strategy

problem = ProblemSpec("problem.p")
schedule = StrategySchedule.single(make_strategy())

result = Prover().run(problem, schedule=schedule)
```

`Prover` constructs a fresh policy from each strategy's policy options.
Policies choose among legal actions provided by `Dynamics`. Successful results
expose the final closed state.

Use this changelog section as the GitHub release body for `0.1.0`.
