# Connections

[![tests](https://github.com/fredrrom/connections/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/connections/actions/workflows/python-app.yml)
[![docs](https://github.com/fredrrom/connections/actions/workflows/pages.yml/badge.svg?branch=main)](https://fredrrom.github.io/connections/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fredrrom/connections/blob/main/LICENSE)

Agentic primitives, provers, and experiments for classical, intuitionistic, and modal first-order logic based on connection tableau. 

Design notes, guides, and the API reference are in the [Docs](https://fredrrom.github.io/connections/).

## Package Layout

The library, `connections`, lives in `src/connections/`; its module map is in
[Architecture](https://fredrrom.github.io/connections/design/architecture/).
The packages built on it, under `packages/`:

- `pycop`: The pyCoP prover tested extensively for inference step order parity with leanCoP 2.0, ileanCoP 1.2, and MleanCoP 1.3.

## Install

```bash
pip install git+https://github.com/fredrrom/connections.git
```

For development, see [Development](docs/src/guides/development.md).

## pycop CLI

Run the pyCoP prover on a TPTP problem:

```bash
uv run pycop Problems/SYN/SYN001+1.p classical
```

Run a single leanCoP strategy:

```bash
uv run pycop Problems/SYN/SYN001+1.p classical \
  --settings cut \
  --settings 'comp(7)'
```

Run a schedule:

```bash
uv run pycop Problems/SYN/SYN001+1.p classical \
  --schedule classical
```

Run over a directory or file list and write corpus rows:

```bash
uv run pycop Problems/SYN --out artifacts/corpus/syn.jsonl --steps 1000 --overwrite
```

Download benchmark corpora:

```bash
uv run pycop-download-benchmarks --list
```

Supported logic arguments are `classical`, `intuitionistic`, `D`, `T`, `S4`,
and `S5`. Supported domain arguments are `constant`, `cumulative`, and
`varying`.

Supported input formats: [TPTP](https://www.tptp.org) `fof` and `cnf` for classical, [ILTP](http://www.iltp.de) `fof` input for intuitionistic, and [QMLTP](http://www.iltp.de/qmltp/) `qmf` input for modal.

## API Use

```python
from connections.interaction import (
    Problem,
    StrategySchedule,
    WeightedStrategy,
    run_schedule,
)
from pycop import LeancopSettingsCodec

problem = Problem(
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

result = run_schedule(problem, schedule=schedule)

print(result.outcome)
print(result.szs_status)
print(result.to_dict())
```

Agents are called with the current state and return the next action:

```python
from connections.agent import Agent

class MyAgent(Agent):
    def __call__(self, state):
        ...
```

An agent returns actions only: `Action | None`. Whether a budget ran out and
what any of it means for the problem are the prover's to decide. The agent's
`status` attribute reports on its own search, and the judge in `interaction`
maps statuses to outcomes and SZS.

`Dynamics` owns legal action generation, `rollout` applies the chosen actions,
and `run_schedule` drives a schedule of rollouts over one problem. Budgets are
best effort; hard time and memory limits belong to whatever runs connections
in a subprocess.

## License

This project is licensed under GNU GPL v3 or later. See `LICENSE`.

The parity harness bundles leanCoP 2.1, ileanCoP 1.2 and MleanCoP 1.3 by
Jens Otten (<https://www.leancop.de>), all under the GNU General Public
License, as correctness oracles. They are not part of the `connections` or
`pycop` API. Four of those files carry local parity instrumentation and are
marked as modified. See
[`packages/pycop/src/pycop/parity/reference_provers/NOTICE.md`](packages/pycop/src/pycop/parity/reference_provers/NOTICE.md)
for the list of changes.

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
