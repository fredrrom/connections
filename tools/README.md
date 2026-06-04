# Developer Tools

`tools/` contains checkout-local developer diagnostics and runnable utilities.
They are not part of the importable `connections` library API, and they are not
normal pytest tests.

These commands may:

- call external programs such as SWI-Prolog
- run over problem corpora
- write JSONL, summaries, profiles, and other artifacts
- take longer than deterministic tests
- be used manually or in release validation

They should not:

- be required by downstream users importing `connections`
- contain project-specific orchestration outside prover diagnostics
- depend on external application code
- be imported by normal tests for correctness coverage

The current tool families are:

- `tools/corpus/`: run a prover over one or more problem files and write rows.
- `tools/parity/`: compare native behavior with leanCoP-family references.
- `tools/profiling/`: measure pycop performance over files or corpora.
- `tools/parity/reference_provers/`: bundled reference prover assets used by
  parity diagnostics.

Use normal tests for deterministic unit and integration checks:

```bash
uv run pytest tests
```

Use tools for explicit diagnostics and release validation:

```bash
uv run python tools/parity/run_all.py --json
uv run python tools/profiling/run.py path/to/problems --out artifacts/profile --overwrite
```

## Parity Triage

Corpus-level parity has three layers:

- `run_matrix_parity.py`: parser plus matrix construction.
- `run_status_check.py`: native SZS status against benchmark labels when
  present, with Prolog reference status as telemetry.
- `run_trace_parity.py`: policy-visible search-event order against the bundled
  reference prover.

For a broad-sweep divergence, start with matrix parity on the problem, then
status checking, then trace parity. Use `diagnose_search.py` when the native
candidate set or rejection reason needs inspection, and profiling when status
and trace behavior are fine but runtime is suspicious.

Manifest runs write one problem row per input plus summary rows. Failed or
classified problem rows include `repro_commands` with argv-style commands for
matrix, status, trace, and native search diagnosis on the same problem.

Classified manifest divergences keep expected reference quirks visible without
counting them as native/reference implementation failures. Common examples are:

- native matched the benchmark status while the Prolog reference timed out.
- native and reference both timed out against a benchmark status under the
  configured budget.
- native and reference agreed with each other but disagreed with the benchmark
  annotation.

Matrix parity normalizes generated Skolem and definition names up to stable
renaming. Classical `conj` rows also normalize away leanCoP's internal `#`
conjecture marker because native matrices store that information as clause
role/start metadata.

See `CONTRIBUTING.md` for the full developer workflow.
