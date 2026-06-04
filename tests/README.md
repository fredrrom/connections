# Test Layout

The test suite is organized by execution boundary.

- `tests/unit/`: isolated tests for in-process code units. These should not
  require external theorem-prover binaries or benchmark corpora.
- `tests/integration/`: tests that cross process, filesystem, CLI, or
  corpus boundaries.

Integration filenames should carry the interaction boundary or scenario, so the
top-level integration directory does not need package-shaped subdirectories.
Current examples:

- `test_entrypoints_*.py`: `pycop` console script and subprocess-level CLI behavior
- `test_corpus_*.py`: corpus-facing parser or pipeline behavior

Directory markers are added automatically by `tests/conftest.py`:

- files under `tests/unit/` get `unit`
- files under `tests/integration/` get `integration`

External requirements are marked explicitly:

- `external_tptp_corpus`: optional tests against a local TPTP checkout

Useful commands:

```bash
uv run pytest tests/unit
uv run pytest tests
uv run pytest -m external_tptp_corpus --tptp-root /path/to/TPTP
```

Corpus-scale prover runs, parity sweeps, and profiling runs live under
`tools/` as explicit developer commands. Keep this test suite deterministic and
small enough for regular local verification.
