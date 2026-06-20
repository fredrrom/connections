# Development Workflow

Use `uv` for local development:

```bash
uv sync --dev --group docs
```

## Normal Checks

Run the deterministic checks before sending changes:

```bash
uv run pytest tests
uv run ruff check .
uv run ty check
uv build
uv run --group docs mkdocs build --strict -f docs/mkdocs.yml
```

The normal checks do not require SWI-Prolog or external benchmark corpora.

## Documentation

Documentation source lives under `docs/src/`. MkDocs uses `docs/mkdocs.yml`.

Preview the site locally:

```bash
uv run --group docs mkdocs serve -f docs/mkdocs.yml
```

Then open <http://127.0.0.1:8000/>.

Build the site:

```bash
uv run --group docs mkdocs build --strict -f docs/mkdocs.yml
```

GitHub Pages uses `.github/workflows/pages.yml` and builds from
`docs/mkdocs.yml`.

## Developer Diagnostics

The `tools/` directory contains checkout-local diagnostics. These commands are
not part of the public `connections` API and should not be imported by package
code.

The Prolog-backed parity commands require `swipl` on `PATH`. They are developer
diagnostics, not normal checks.

Run the fixed parity suite:

```bash
uv run python tools/parity/run_all.py --json
```

Focused parity commands:

```bash
uv run python tools/parity/run_prefix_parity.py --json
uv run python tools/parity/run_prefix_equation_parity.py --json
uv run python tools/parity/run_free_variable_admissibility_parity.py --json
uv run python tools/parity/run_matrix_parity.py --json
uv run python tools/parity/run_status_check.py --json
uv run python tools/parity/run_trace_parity.py --json
```

Do not edit the bundled Prolog reference provers under
`tools/parity/reference_provers/`. Local SWI-Prolog compatibility adapters
belong under `tools/parity/prolog/`.

## Manifest Sweeps

Run status or matrix sweeps from manifests:

```bash
uv run python tools/parity/run_manifest.py \
  --out artifacts/parity/status/full-0.1.jsonl \
  --summary-out artifacts/parity/status/full-0.1.summary.json \
  --overwrite

uv run python tools/parity/run_manifest.py \
  --manifest tools/parity/manifests/matrix-0.1.json \
  --out artifacts/parity/matrix/full-0.1.jsonl \
  --summary-out artifacts/parity/matrix/full-0.1.summary.json \
  --overwrite
```

Use `--limit`, `--offset`, and `--only` for reproducible smaller slices.

## Full Trace Diagnostics

Run a classical trace sweep against leanCoP 2.1:

```bash
uv run python tools/parity/run_trace_parity.py \
  --path ../benchmarks/TPTP-v6.4.0/Problems \
  --source-dir ../benchmarks/TPTP-v6.4.0 \
  --timeout 1 \
  --logic classical \
  --reference leancop21 \
  --settings def \
  --settings conj \
  --settings nodef \
  --settings scut \
  --settings cut \
  --settings 'comp(7)' \
  --omit-traces \
  --out artifacts/release-0.1/full-tptp-trace-1s/rows.jsonl \
  --overwrite
```

Summarize the JSONL rows:

```bash
uv run python tools/parity/summarize_trace_rows.py \
  artifacts/release-0.1/full-tptp-trace-1s/rows.jsonl
```

The useful trace-parity release numbers are:

- supported rows
- unsupported parser rows
- native-only timeouts
- reference-only timeouts
- status disagreements
- trace disagreements where neither side timed out

## Corpus Runs

Run native `pycop` over a problem slice:

```bash
uv run pycop Problems/SYN \
  --out artifacts/corpus/syn.jsonl \
  --settings cut \
  --settings 'comp(7)' \
  --steps 1000 \
  --timeout 10 \
  --overwrite
```

## Profiling

Profile a corpus slice:

```bash
uv run pycop Problems/SYN \
  --profile artifacts/profile/syn-cut-comp7 \
  --settings cut \
  --settings 'comp(7)' \
  --steps 1000 \
  --timeout 10 \
  --overwrite
```

Profiling output and corpus rows are written under `artifacts/`, which is
ignored by Git.
