# Connections

[![tests](https://github.com/fredrrom/connections/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/fredrrom/connections/actions/workflows/python-app.yml)
[![docs](https://github.com/fredrrom/connections/actions/workflows/pages.yml/badge.svg?branch=main)](https://fredrrom.github.io/connections/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/fredrrom/connections/blob/main/LICENSE)

Agentic primitives, provers, and experiments for classical, intuitionistic, and modal first-order logic based on connection tableau. 

Design notes, guides, and the API reference are in the [Docs](https://fredrrom.github.io/connections/).

## Content 

In addition to the prover primitive library, [`connections`](src/connections/), the repo hosts some projects built on it, under [`packages/`](packages/):

- [`pycop`](packages/pycop/): The pyCoP prover tested extensively for inference step order parity with [leanCoP 2.0](https://www.leancop.de), [ileanCoP 1.2](https://www.leancop.de/ileancop/), and [MleanCoP 1.3](https://www.leancop.de/mleancop/).
- [`imitation`](packages/imitation/): Imitation learning prover and experiments based on GNN function approximation.

## Install

```bash
pip install git+https://github.com/fredrrom/connections.git
```

For development, see [Development](docs/src/guides/development.md).

## License

This project is licensed under GNU GPL v3 or later. See `LICENSE`.

The parity harness bundles leanCoP 2.1, ileanCoP 1.2 and MleanCoP 1.3 by
Jens Otten (<https://www.leancop.de>), all under the GNU General Public
License, as correctness oracles. They are not part of the `connections` or
`pycop` API. Four of those files carry local parity instrumentation and are
marked as modified. See
[`packages/pycop/src/pycop/parity/reference_provers/NOTICE.md`](packages/pycop/src/pycop/parity/reference_provers/NOTICE.md)
for the list of changes.

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
