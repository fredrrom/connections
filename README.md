# Connections

[![tests](https://github.com/fredrrom/connections/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/connections/actions/workflows/python-app.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fredrrom/connections/blob/main/LICENSE)

`connections` provides classical, intuitionistic, and modal connection-tableaux
construction primitives for proof-search control. It
contains a small prover core, reusable search policies, native
FOF/CNF/QMF matrix construction, and `pycop`, a reimplementation of leanCoP 2.1,
iLeanCoP 1.3, and mLeanCoP 1.2 in this same framework tested extensively for
proof-step parity.


## Package Layout

- `connections.prover`: prover loop, state, dynamics, actions, strategies, hooks,
  and result types
- `connections.policy`: DFS and iterative-deepening policies
- `connections.pycop`: leanCoP-family pycop strategies, schedules, settings,
  and CLI
- `connections.constraints`: term and prefix unification, free-variable
  constraints
- `connections.clausification`: file-to-matrix construction
- `tools/`: local developer diagnostics for corpus runs, profiling, and
  leanCoP-family parity checks

`tools/` is not part of the public package API.

## Install

```bash
pip install git+https://github.com/fredrrom/connections.git
```

For development:

```bash
git clone https://github.com/fredrrom/connections.git
cd connections
uv sync --dev
```

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

Supported logic arguments are `classical`, `intuitionistic`, `D`, `T`, `S4`,
and `S5`. Supported domain arguments are `constant`, `cumulative`, and
`varying`.

Native 0.1 matrix construction supports classical `fof` and `cnf`
input, intuitionistic ILTP `fof` input, and modal QMLTP `qmf` input.

## API Use

```python
from connections.prover import Prover, StrategySchedule, WeightedStrategy
from connections.pycop.strategy import PycopStrategy

schedule = StrategySchedule.from_weighted(
    [WeightedStrategy(PycopStrategy(), weight=1)],
    steps=1000,
    timeout_seconds=5.0,
)

result = Prover().run(
    "Problems/SYN/SYN001+1.p",
    schedule=schedule,
    logic="classical",
    domain="constant",
    source_file_dirs=("/path/to/TPTP",),
)

print(result.outcome)
print(result.szs_status)
```

Policies implement action choice:

```python
from connections.policy import Policy

class FirstActionPolicy(Policy):
    def available_actions(self, state):
        ...

    def next_action(self, state, actions):
        return actions[0]
```

`Prover` executes the selected action. `Dynamics` owns legal action generation.
Hooks observe choices, transitions, proof discovery, and strategy completion.

## Docs

The documentation source lives in `docs/src/` and is built with MkDocs from
`docs/mkdocs.yml`. Local generated HTML is written to `docs/site/`. GitHub
Pages builds the deploy artifact from the same config using
`.github/workflows/pages.yml`.

Preview locally:

```bash
uv run --group docs mkdocs serve -f docs/mkdocs.yml
```

Then open <http://127.0.0.1:8000/>.

- [Prover API](docs/src/prover-api.md)
- [State and Dynamics](docs/src/state-dynamics.md)
- [Unification and Constraints](docs/src/unification.md)
- [TPTP Parser](docs/src/tptp-parser.md)
- [Corpus and Parity Tools](docs/src/corpus-and-parity-tools.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Developer Validation

Fast local checks:

```bash
uv run pytest tests
uv run ruff check .
uv run ty check
uv run --group docs mkdocs build --strict -f docs/mkdocs.yml
```

Curated parity checks against bundled reference provers:

```bash
uv run python tools/parity/run_all.py --json
```

Classical trace-parity diagnostic against leanCoP:

```bash
uv run python tools/parity/run_trace_parity.py \
  --path ../benchmarks/TPTP-v6.4.0/Problems \
  --source-dir ../benchmarks/TPTP-v6.4.0 \
  --limit 100 \
  --timeout 20 \
  --step-limit 5000 \
  --logic classical \
  --reference leancop21 \
  --settings def \
  --settings conj \
  --settings nodef \
  --settings scut \
  --settings cut \
  --settings 'comp(7)' \
  --omit-traces \
  --out artifacts/release-0.1/tptp-trace.jsonl \
  --overwrite
```

The Prolog-backed parity diagnostics require `swipl` on `PATH`; the fast local
checks above do not.

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
