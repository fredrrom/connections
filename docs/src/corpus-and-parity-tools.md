# Corpus And Parity Tools

`connections/tools/` contains developer commands for validating and measuring
the prover. These tools are not part of the public `connections` API, and they
are not imported by the library package.

## Corpus Runner

Download benchmark corpora with:

```bash
python tools/corpus/download.py --list
python tools/corpus/download.py tptp-v6.4.0 iltp qmltp --root benchmarks
```

Use `--all` to download every known corpus and `--force` to replace existing
targets. Archives are cached under `ROOT/.downloads` by default.

The first corpus tool is:

```bash
python tools/corpus/run.py PATH --out artifacts/corpus/runs.jsonl --overwrite
```

It selects problem files from one or more paths, runs pycop over each problem,
and writes one JSONL row per problem. It also writes a summary sidecar by
default: `artifacts/corpus/runs.summary.json`.

Useful options:

```bash
python tools/corpus/run.py Problems/SYN \
  --out artifacts/corpus/syn.jsonl \
  --pattern "*.p" \
  --limit 25 \
  --settings cut \
  --settings "comp(7)" \
  --steps 1000 \
  --timeout 10 \
  --continue-on-error \
  --overwrite
```

Use `--summary-out PATH` to choose the summary path, or `--no-summary` when
only JSONL rows should be written.

The output row schema is intentionally small and stable:

- `problem`
- `path`
- `status`
- `outcome`
- `szs_status`
- `inference_actions`
- `elapsed_seconds`
- `strategy_count`
- `winning_strategy_index`
- `error_type`
- `error_message`

The runner is generic internally: `tools.corpus.run.run_corpus` accepts a
`prover_factory`, a schedule, source directories, and problem paths. The CLI
currently exposes pycop because that is the built-in prover line.

The summary schema is:

- `schema`
- `output`
- `summary_output`
- `problems`
- `theorem`
- `unsatisfiable`
- `counter_satisfiable`
- `satisfiable`
- `timeout`
- `gave_up`
- `error`
- `inference_actions`

## Boundary

Corpus running belongs in `connections` because it is basic prover validation
and measurement infrastructure. The tool owns file selection and generic prover
execution; callers choose paths, schedules, settings, and output locations.

## Profiling

The profiling tool also lives in `connections`:

```bash
python tools/profiling/run.py PATH --out artifacts/profile --overwrite
```

It selects problem files, runs pycop under `cProfile`, and writes:

- `profile.pstats`
- `runs.jsonl`
- `profile_functions.jsonl`
- `profile_callers.jsonl`
- `profile_overview.json`
- `summary.json`

When no `--settings` tokens are supplied, the profiler uses the built-in pycop
schedule for the selected logic. When settings are supplied, it profiles that
single pycop strategy:

```bash
python tools/profiling/run.py Problems/SYN \
  --out artifacts/profile/syn-cut-comp7 \
  --settings cut \
  --settings "comp(7)" \
  --steps 1000 \
  --timeout 10 \
  --overwrite
```

The profiling logic stays here because it is developer measurement
infrastructure for the prover.

## Parity

Reference-prover and parity tools live beside the corpus runner. They are
developer diagnostics, not package APIs:

```text
tools/
  parity/
    reference_provers/
    prefix_oracle.py
    run_all.py
    run_prefix_parity.py
    run_prefix_equation_parity.py
    run_free_variable_admissibility_parity.py
    run_matrix_parity.py
    run_trace_parity.py
    run_status_check.py
```

They use bundled leanCoP, ileanCoP, and mleanCoP code as correctness oracles.
These tools may require SWI-Prolog and corpora, so they should remain
explicit developer commands rather than normal pytest tests.

The three corpus-level checks are:

- **status**: run native `pycop` and compare its SZS status with the benchmark
  ground-truth label when one is available.
- **matrix**: compare native parsing plus matrix construction with the
  leanCoP-family translator output.
- **trace**: compare native search events with the bundled reference prover
  search events.

The lower-level prefix, prefix-equation, and free-variable admissibility checks
are oracle diagnostics for the constraint machinery used by matrix construction
and proof search.

Reference Prolog assets are copied under:

```text
tools/parity/reference_provers/prolog/
```

Do not edit the copied reference-prover files. SWI-Prolog adapters and other
local parity helpers belong under `tools/parity/prolog/`.

The umbrella validation command runs the curated prefix, matrix, status, and
trace diagnostics:

```bash
python tools/parity/run_all.py --json
```

It runs the direct prefix, prefix-equation, free-variable admissibility,
source-to-matrix parity, benchmark-status checking, and trace parity commands.
Use `--only` or `--skip` for focused runs:

```bash
python tools/parity/run_all.py --only matrix --json
python tools/parity/run_all.py --skip trace --json
```

Manifest sweeps run larger configured corpus slices. The default manifest is
`tools/parity/manifests/full-0.1.json`:

```bash
python tools/parity/run_manifest.py --json
```

The source-to-matrix manifest is separate:

```bash
python tools/parity/run_manifest.py \
  --manifest tools/parity/manifests/matrix-0.1.json \
  --json
```

Manifest runs can also write durable artifacts:

```bash
python tools/parity/run_manifest.py \
  --out artifacts/parity/status/full-0.1.jsonl \
  --summary-out artifacts/parity/status/full-0.1.summary.json \
  --overwrite
```

The direct prefix-unification oracle is:

```bash
python tools/parity/prefix_oracle.py
```

Native-vs-reference prefix diagnostics are:

```bash
python tools/parity/run_prefix_parity.py
python tools/parity/run_prefix_equation_parity.py
python tools/parity/run_free_variable_admissibility_parity.py
```

Curated status and trace checks are:

```bash
python tools/parity/run_status_check.py
python tools/parity/run_trace_parity.py
```

Both can run a small file or corpus slice:

```bash
python tools/parity/run_status_check.py \
  --path Problems/SYN \
  --source-dir path/to/TPTP-root \
  --logic classical \
  --reference leancop21 \
  --settings cut \
  --settings "comp(7)" \
  --limit 25 \
  --json
```

Without `--omit-traces`, each JSON row includes both full event arrays. That is
useful for a single problem or a small slice, but corpus-scale sweeps should
write compact rows with only statuses, trace lengths, timings, match flags, and
the first difference.

The source-to-matrix command is:

```bash
python tools/parity/run_matrix_parity.py --json
```

It normalizes native matrices and reference translator output up to variable
renaming and compares both order-sensitive and multiset views of clauses.
This is the parser plus matrix-construction parity loop for the supported
classical FOF, classical CNF, intuitionistic FOF, and modal QMF slices.

Triage guidance and classification conventions are documented in
`tools/README.md` and `CONTRIBUTING.md`.
