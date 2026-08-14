# pycop

A leanCoP-equivalent prover over `connections`: the strategies, the CLI, and the
parity harness that checks the equivalence claim.

The aim is parity of effective behaviour, not line-by-line reproduction of
Prolog control. Matrix preprocessing owns translation, conjecture-start
behaviour, and ordering; the policy owns depth-first continuation, iterative
deepening, cut and scut, start selection, and open-leaf selection; the calculus
owns legality, unification, regularity, factorization scope, and undo.

## The command

```bash
uv run pycop path/to/problem.p
```

See [prove a problem](../guides/prove-a-problem.md) for the flags. The CLI owns
argument parsing, schedule selection, SZS on stdout, and the exit code -- one
problem per invocation, which is the shape CASC asks for.

## Corpus runs

Point it at a tree and write one JSONL row per problem:

```bash
uv run pycop Problems/SYN \
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

A summary sidecar is written alongside by default; `--summary-out PATH` moves it
and `--no-summary` suppresses it.

Row fields:

    problem  path  status  outcome  szs_status
    inference_actions  elapsed_seconds
    strategy_count  winning_strategy_index
    error_type  error_message

Some of these are facts about the proof and come from the `Result`; others --
`elapsed_seconds`, `path` -- are facts about this execution and are added here.
That split is deliberate: `connections` returns what only it can know, and the
runner adds the rest. See [running](../design/running.md#results).

Benchmark corpora:

```bash
pycop-download-benchmarks --list
pycop-download-benchmarks tptp-v6.4.0 iltp qmltp --root benchmarks
```

## Profiling

```bash
uv run pycop Problems/SYN \
  --profile artifacts/profile/syn-cut-comp7 \
  --settings cut \
  --settings "comp(7)" \
  --steps 1000 \
  --timeout 10 \
  --overwrite
```

Writes `profile.pstats`, `runs.jsonl`, `profile_functions.jsonl`,
`profile_callers.jsonl`, `profile_overview.json` and `summary.json`.

With no `--settings`, the built-in schedule for the selected logic is profiled.
With settings, that single strategy is.

## Parity

Developer diagnostics, not tests: they need SWI-Prolog on `PATH` and a corpus,
so they stay explicit commands rather than running under pytest.

Bundled leanCoP, ileanCoP and mleanCoP serve as correctness oracles. Three
corpus-level checks:

| | |
|---|---|
| **status** | native SZS status against the benchmark's ground-truth label |
| **matrix** | native parsing and matrix construction against the reference translator |
| **trace** | native search events against the reference prover's search events |

with lower-level oracle checks for the constraint machinery -- direct prefix
unification, prefix equations, and free-variable admissibility.

```bash
uv run python -m pycop.parity.run_all --json
uv run python -m pycop.parity.run_all --only matrix --json
uv run python -m pycop.parity.run_all --skip trace --json
```

Manifest sweeps run larger configured slices and can write durable artifacts:

```bash
uv run python -m pycop.parity.run_manifest \
  --out artifacts/parity/status/full-0.1.jsonl \
  --summary-out artifacts/parity/status/full-0.1.summary.json \
  --overwrite
```

A full classical trace sweep:

```bash
uv run python -m pycop.parity.run_trace_parity \
  --path ../benchmarks/TPTP-v6.4.0/Problems \
  --source-dir ../benchmarks/TPTP-v6.4.0 \
  --timeout 1 \
  --logic classical \
  --reference leancop21 \
  --settings def --settings conj --settings nodef \
  --settings scut --settings cut --settings 'comp(7)' \
  --omit-traces \
  --out artifacts/release-0.1/full-tptp-trace-1s/rows.jsonl \
  --overwrite
```

Without `--omit-traces` each row carries both full event arrays, which is right
for one problem and wrong for a sweep -- corpus-scale runs should keep statuses,
trace lengths, timings, match flags, and the first difference.

The numbers worth reporting from a sweep: supported rows, unsupported parser
rows, native-only timeouts, reference-only timeouts, status disagreements, and
trace disagreements where neither side timed out.

Matrix parity normalises both sides up to variable renaming and compares
order-sensitive and multiset views, covering the classical FOF, classical CNF,
intuitionistic FOF, and modal QMF slices.

### Bundled reference provers

The oracles are Jens Otten's, vendored so parity is reproducible against a fixed
reference rather than whatever is installed:

| | | |
|---|---|---|
| leanCoP 2.1 | classical | <https://www.leancop.de> |
| ileanCoP 1.2 | intuitionistic | <https://www.leancop.de/ileancop/> |
| MleanCoP 1.3 | modal D, T, S4, S5 | <https://www.leancop.de/mleancop/> |

All under the GNU General Public License, which `connections` and `pycop` are
compatible with as GPL-3.0-or-later.

Four files carry local instrumentation -- trace events and step budgets, so a
reference run emits the same search events the native prover does, which is what
makes trace parity checkable. They are marked as modified in their headers.
Provenance, copyright ranges, the file inventory, and the change list are in
`reference_provers/NOTICE.md`.

!!! warning "Reference assets are read-only"

    Do not edit the bundled provers further. SWI-Prolog compatibility adapters
    and other local helpers belong in `pycop/parity/prolog/`, beside
    `swi_compat.pl` and `matrix_dump.pl`. Any change that does land in a vendored
    file must be recorded in its header and in `NOTICE.md` -- the GPL requires
    modified files to say so and to carry a date.

