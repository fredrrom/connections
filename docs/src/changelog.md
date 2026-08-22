# Changelog

## 0.1.0 - Unreleased

Initial prover-loop release.

### Added

- `run_schedule`, `build_state` and `rollout` as the entry points, over `calculus` for
  the transition system and `run` for everything above it. Agents implement
  policies: `Agent` is percept-in action-out, `AgentStatus` its word about its
  own search, and the judge in `interaction` produces outcomes and SZS from outside
  the agent. `MarkovAgent`, `OnlineDFSAgent` and `OnlineIDAgent` take a
  chooser and `AgentOptions`; a learned agent is a different chooser.
- Public action records under `connections.calculus.actions`.
- Corpus selection, run rows, summaries and profiling in `pycop.runs`.
- DFS and iterative-deepening policy components with first-action default
  selection.
- Transactional term, prefix, and free-variable constraint stores.
- Native TPTP parsing for `fof`, `cnf`, `qmf`, and `include`.
- Native matrix construction for the 0.1 classical FOF/CNF slice and an
  initial prefix-annotated non-classical slice.
- `pycop` CLI with settings, schedules, source directories, trace output,
  corpus JSONL output, and budget options.
- `pycop-download-benchmarks` CLI for benchmark setup.
- `pycop.parity` diagnostics for leanCoP-family parity checks.
- MkDocs documentation under `docs/`.

### Public Boundary

The main API is:

```python
from connections.interaction import Problem, Result, StrategySchedule, run_schedule

problem = Problem("problem.p")
schedule = StrategySchedule.single(make_strategy())

result: Result = run_schedule(problem, schedule=schedule)
result.szs_status
result.to_dict()
```

`run` handles one problem and returns a `Result`; `Result.to_dict` is the
serialisation contract. Below it, `rollout(state, policy=...)` is a policy
acting in *P(M)* from a state, and `build_state` is where a file becomes one.

A fresh policy is constructed from each strategy's policy options. Policies
choose among the actions `Dynamics` admits, and a successful result exposes the
final closed state.

Use this changelog section as the GitHub release body for `0.1.0`.
