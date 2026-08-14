# pycop

A leanCoP-equivalent connection prover built on
[`connections`](https://github.com/fredrrom/connections), with the parity
harness that checks the equivalence claim against the leanCoP family.

```bash
uv run pycop path/to/problem.p
```

The aim is parity of effective behaviour, not line-by-line reproduction of
Prolog control. Matrix preprocessing owns translation, conjecture-start
behaviour, and ordering; the policy owns depth-first continuation, iterative
deepening, cut and scut, start selection, and open-leaf selection; the calculus
owns legality, unification, regularity, factorization scope, and undo.

Documentation: <https://fredrrom.github.io/connections/packages/pycop/>

## Contents

    src/pycop/
        cli.py            argument parsing, schedule selection, SZS, exit code
        schedule.py       named strategy schedules
        settings_codec.py leanCoP-style settings
        runs/             corpus selection, run rows, profiling, benchmarks
        parity/           the reference-prover harness

## Bundled reference provers

`parity/` vendors three leanCoP-family provers as correctness oracles, so parity
results are reproducible against a fixed reference rather than whatever happens
to be installed:

| | | |
|---|---|---|
| leanCoP 2.1 | classical | <https://www.leancop.de> |
| ileanCoP 1.2 | intuitionistic | <https://www.leancop.de/ileancop/> |
| MleanCoP 1.3 | modal D, T, S4, S5 | <https://www.leancop.de/mleancop/> |

All three are by **Jens Otten** and distributed under the **GNU General Public
License**. `pycop` is GPL-3.0-or-later, so redistributing them here is
compatible. They are not part of the `pycop` or `connections` API.

Four of those files are modified. We added trace events and step budgets so a
reference run emits the same search events the native prover does, which is what
makes trace parity checkable at all; the instrumentation does not change the
search these provers perform. Each modified file says so in its header.

Provenance, copyright ranges, the full file inventory, and the list of changes
are in
[`src/pycop/parity/reference_provers/NOTICE.md`](src/pycop/parity/reference_provers/NOTICE.md).

If you are citing the reference provers rather than this software, cite Otten's
papers for the respective systems.

## Parity

Developer diagnostics rather than tests: they need SWI-Prolog on `PATH` and a
problem corpus.

```bash
uv run python -m pycop.parity.run_all --json
uv run python -m pycop.parity.run_all --only matrix --json
```

## License

GPL-3.0-or-later. See `LICENSE` in the repository root.
