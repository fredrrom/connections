# Connections

[![tests](https://github.com/fredrrom/connections/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/connections/actions/workflows/python-app.yml)
[![docs](https://github.com/fredrrom/connections/actions/workflows/pages.yml/badge.svg?branch=main)](https://fredrrom.github.io/connections/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fredrrom/connections/blob/main/LICENSE)

Primitives for building agentic provers based on connection tableaux, in classical, intuitionistic, and modal first-order logic, and experiments based on them. 

Design notes, guides, and the API reference are in the [docs](https://fredrrom.github.io/connections/).

## Quick start: prove a problem

With [uv](https://docs.astral.sh/uv/) installed:

```bash
git clone https://github.com/fredrrom/connections
cd connections
uv run --package pycop pycop examples/socrates.p
# Theorem
```

## Start here

| Goal | Guide |
|---|---|
| Prove a problem | [CLI and Python entry points](docs/src/guides/prove-a-problem.md) |
| Build a search agent | [Write an agent](docs/src/guides/write-an-agent.md) |
| Reproduce the learning experiments | [Imitation package](packages/imitation/README.md) |
| Understand the system | [Architecture](docs/src/design/architecture.md) |
| Contribute | [Development guide](docs/src/guides/development.md) |

## What's included

| Component | Purpose |
|---|---|
| [`connections`](src/connections/) | States, actions, dynamics, constraints, parsing, and clausification for connection-tableau construction. |
| [`pycop`](packages/pycop/) | A native Python prover whose inference-step ordering is checked for trace equality against the bundled [leanCoP 2.1](https://www.leancop.de), [ileanCoP 1.2](https://www.leancop.de/ileancop/), and [MleanCoP 1.3](https://www.leancop.de/mleancop/) reference provers. |
| [`imitation`](packages/imitation/) | GNN-based imitation-learning agents and the experiments built on `connections`. |

## Install the core library

If you want to build on the prover primitives without installing `pycop` or
the learning package:

```bash
pip install git+https://github.com/fredrrom/connections.git
```

This installs only `connections`. To use the prover, follow the quick start
above. For a development checkout, see [Development](docs/src/guides/development.md).

## Papers

This repo is the code home of the following papers:

- *Imitation Learning for Connection-Tableau Construction*
  (Rømming et al.; [arXiv:2608.26009](https://arxiv.org/abs/2608.26009), 2026).
  The transition system and agents are the [`connections`](src/connections/)
  library; the graph neural network, critic, trainer, and experiments are
  [`imitation`](packages/imitation/).
- *Connections: Markov Decision Processes for Classical, Intuitionistic and
  Modal Connection Calculi*
  (Rømming, Otten, Holden; [AReCCa 2023](https://ceur-ws.org/Vol-3613/)).
  The library this repo grew from, now [`connections`](src/connections/);
  the citation is below.

## Citation

For the imitation learning provers and experiments:

```bibtex
@misc{imitation_2026,
    author        = {Rømming, Fredrik and Bakšys, Mantas and
                     Fixman, Martin S. and Holden, Sean B.},
    title         = {Imitation Learning for Connection-Tableau Construction},
    year          = {2026},
    eprint        = {2608.26009},
    archivePrefix = {arXiv},
    primaryClass  = {cs.AI},
}
```

For the library and its calculi:

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

## License

This project is licensed under GNU GPL v3 or later. See [`LICENSE`](LICENSE).

The parity harness bundles leanCoP 2.1, ileanCoP 1.2 and MleanCoP 1.3 by
Jens Otten (<https://www.leancop.de>), all under the GNU General Public
License, as correctness oracles. They are not part of the `connections` or
`pycop` API. Four of those files carry local parity instrumentation and are
marked as modified. See
[`packages/pycop/src/pycop/parity/reference_provers/NOTICE.md`](packages/pycop/src/pycop/parity/reference_provers/NOTICE.md)
for the list of changes.
