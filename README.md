# Connections

[![tests](https://github.com/fredrrom/connections/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/connections/actions/workflows/python-app.yml)
[![docs](https://github.com/fredrrom/connections/actions/workflows/pages.yml/badge.svg?branch=main)](https://fredrrom.github.io/connections/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fredrrom/connections/blob/main/LICENSE)

`connections` provides classical, intuitionistic, and modal connection-tableaux
construction primitives for proof-search control. It
contains a small prover loop, reusable search policies, native
FOF/CNF/QMF matrix construction, and `pycop`, a reimplementation of leanCoP 2.1,
iLeanCoP 1.3, and mLeanCoP 1.2 in this same framework tested extensively for
proof-step parity.


## Package Layout

- `connections.prover`: prover loop, state, dynamics, actions, strategies, and
  result types
- `connections.runs`: reusable corpus selection, prover-run rows, summaries,
  and generic corpus execution
- `connections.policy`: DFS and iterative-deepening policies
- `provers.pycop`: leanCoP-family pycop strategies, schedules, settings,
  and CLI
- `connections.constraints`: term and prefix unification, free-variable
  constraints
- `connections.clausification`: file-to-matrix construction
- `tools/`: local leanCoP-family parity diagnostics

`tools/` is not part of the public package API.

## Install

```bash
pip install git+https://github.com/fredrrom/connections.git
```

For development, see [Development Workflow](docs/src/development.md).

## pycop CLI

Run the built-in prover on a TPTP problem:

```bash
pycop Problems/SYN/SYN001+1.p classical
```

Run a single leanCoP strategy:

```bash
pycop Problems/SYN/SYN001+1.p classical \
  --settings cut \
  --settings 'comp(7)'
```

Run a schedule:

```bash
pycop Problems/SYN/SYN001+1.p classical \
  --schedule classical
```

Run over a directory or file list and write corpus rows:

```bash
pycop Problems/SYN --out artifacts/corpus/syn.jsonl --steps 1000 --overwrite
```

Download benchmark corpora:

```bash
connections-download-benchmarks --list
```

Supported logic arguments are `classical`, `intuitionistic`, `D`, `T`, `S4`,
and `S5`. Supported domain arguments are `constant`, `cumulative`, and
`varying`.

Native 0.1 matrix construction supports classical `fof` and `cnf`
input, intuitionistic ILTP `fof` input, and modal QMLTP `qmf` input.

## API Use

```python
from connections.prover import (
    ProblemSpec,
    Prover,
    StrategySchedule,
    WeightedStrategy,
)
from provers.pycop import LeancopSettingsCodec

problem = ProblemSpec(
    "Problems/SYN/SYN001+1.p",
    logic="classical",
    domain="constant",
    source_file_dirs=("/path/to/TPTP",),
)
strategy = LeancopSettingsCodec.from_tokens(["cut", "comp(7)"])
schedule = StrategySchedule.from_weighted(
    [WeightedStrategy(strategy, weight=1)],
    steps=1000,
    timeout_seconds=5.0,
)

result = Prover().run(
    problem,
    schedule=schedule,
)

print(result.outcome)
print(result.szs_status)
```

Policies are called with the current state and return the next action:

```python
from connections.policy import Policy

class MyPolicy(Policy):
    def __call__(self, state):
        ...
```

Plain policies return `Action | None`. Search policies such as DFS and ID may
return `ProverOutcome` when their search space is exhausted. `Prover` executes
the selected action. `Dynamics` owns legal action generation.

## Docs

- [Prover API](docs/src/prover-api.md)
- [State and Dynamics](docs/src/state-dynamics.md)
- [Unification and Constraints](docs/src/unification.md)
- [TPTP Parser](docs/src/tptp-parser.md)
- [Corpus and Parity Tools](docs/src/corpus-and-parity-tools.md)
- [Development Workflow](docs/src/development.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

This project is licensed under GNU GPL v3 or later. See `LICENSE`.

Third-party reference prover assets under `tools/parity/reference_provers/` are
kept for local parity diagnostics and are not part of the public package API.

## Citation

```bibtex
@inproceedings{connections_2023,
    author     = {Rømming, Fredrik and Otten, Jens and Holden, Sean B.},
    title      = {Connections: {Markov} {Decision} {Processes} for {Classical},
                  {Intuitionistic} and {Modal} {Connection} {Calculi}},
    booktitle  = {Proceedings of the First International Workshop on
                  Automated Reasoning with Connection Calculi (AReCCa)},
    series     = {{CEUR} {Workshop} {Proceedings}},
    volume     = {3613},
    year       = {2023},
    pages      = {107--118},
}
```
