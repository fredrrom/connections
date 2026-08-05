# Architecture: what belongs where

This repository is a uv workspace. `connections` is the library; the packages
under `packages/` are built on it. This note records where the boundaries are
and, more usefully, *why* they are there, because several of them are not
obvious and were settled by argument rather than by taste.

## The line

> Everything inside one invocation of a prover is `connections`.
> Everything that exists only because you are running an *experiment* is
> orchestration.

The test is CASC's standard division: one problem, one process, a status on
stdout. Everything needed for that is below the line. Sharding, artifact trees,
claims, resume and fleets are not needed for it, and are above.

A second test, equivalent and sometimes easier to apply: **below the line
produces values, above the line persists them.**

## `Prover` is the system boundary, not a primitive

`Prover` is what CASC calls an ATP system. It clausifies a problem file into an
initial state, runs a schedule of strategies under budgets, and reports an SZS
status. It is not the proof procedure -- that is a policy acting in the
transition system -- and it is not a small composable part.

Reading it as a primitive causes a specific confusion: sharding a corpus
outside `Prover` feels like a layering violation, when in fact CASC itself
shards. The standard division *is* "invoke the system once per problem".

The named provers are configurations of it:

| | |
|---|---|
| `pycop` | `Prover` + leanCoP strategies + a CLI |
| `ilcop` | `Prover` + intuitionistic configuration |
| `satcop` | `Prover` + SAT shadow and `Reset` |

The composable primitive below `Prover` is one strategy on one problem under
one budget. It exists as `_StrategyRun` and is private, because only the
schedule loop has ever needed it. Learning will want it public: GRPO samples
several attempts on the same problem with the same strategy, and repeating
clausification and SZS mapping for each would be waste.

## Two invocation shapes, matching CASC

```python
Prover().run(problem, schedule=...)        # standard division: one problem
Prover().run_multi(problems, schedule=...) # LTB: a batch, one process
```

These are not two designs. CASC defines both: the standard division passes a
problem path per invocation, the Large Theory Batch division passes a batch
specification file and explicitly permits training and memorisation across the
batch. Learning work is LTB-shaped, which is why `run_multi` matters here and
why caching across problems is legitimate in it.

## Statelessness and cache lifetime

`Prover` holds no state. Configuration is passed at the call, and every cache
is a local whose lifetime is the enclosing call:

| cache | lives in | shared across |
|---|---|---|
| matrix | `run` | the strategies of one schedule |
| parsed includes | `run_multi` | the problems of one batch |
| loaded policy | `run_multi` | the problems of one batch |

The rule is uniform: *cache lifetime equals the enclosing call*. It is worth
stating because the alternative is tempting and worse. Making configuration
instance state buys only the avoidance of a model reload between shards --
about a second against a shard of minutes -- and costs thread-safety, a cache
invalidation question (what happens on a second call with a different
schedule?), and a lifecycle.

The matrix cache is keyed by problem and matrix options, so it *could* be
lifted across problems. It should not be: within a corpus run each problem is
attempted once per configuration, so a wider cache would only ever miss. The
sharing that pays is across the strategies of a schedule, which is what it
already does.

## Budgets are semantic; allocation is not

Steps, memory and time change what the search *does*, so they belong to the
prover. Cores, nodes and concurrency change only how fast the same work
happens, so they belong to orchestration.

The three budgets are not equivalent, and each fails a different property:

| budget | portable across machines | prover can enforce it itself |
|---|---|---|
| steps | yes | yes |
| memory | yes | only via `RLIMIT_AS`, which is unreliable when a large virtual mapping (torch) dwarfs RSS, and a no-op on macOS |
| time | **no** | yes |

Only steps is both, which is why it is the effort measure to report. Wall clock
is not portable: the same limit is a different budget on different hardware,
so a corpus run spread over two node types has a coverage number that is partly
a measurement of the cluster. Where a wall-clock limit is used, records must
carry the host, or a `Timeout` cannot be interpreted afterwards.

### Nested limits

A runner should set its own limits *outside* the prover's, derived from them so
they cannot drift apart:

```python
hard_deadline_seconds = 1.5 * timeout_seconds + 60
```

The inner limit is semantic: the prover notices it and reports a status. The
outer limit is operational: if it fires, the prover failed to respect its own
limit, which is a hang. That must not be recorded as `Timeout` -- doing so
buries a bug among legitimately slow problems.

## SZS: who reports what

SZS is the boundary's output contract, and its ontology already has the
distinctions needed. `ResourceOut` covers a resource running out, with
`Timeout` and `MemoryOut` as the specific cases, and `GaveUp` for a system
stopping of its own accord.

The division of labour is forced by *who is alive to speak*:

- The prover reports what it observes: a proof, an exhausted search space, its
  own step budget (`ResourceOut`), its own wall clock (`Timeout`), its own
  memory cap (`MemoryOut`), internal errors.
- The runner reports only when the process died without producing a status. It
  usually cannot know why, so the honest output is an error status plus the
  evidence -- signal, elapsed time, peak RSS -- rather than a guess.

Two rules follow. The runner **refines, never overwrites**: a prover that
returned `Theorem` before a watchdog fired still returned `Theorem`. And a
hard-deadline kill is an error, not a `Timeout`.

`StepBudget` maps to `ResourceOut` rather than `GaveUp`. Both readings are
defensible -- a step budget is self-imposed, which is what `GaveUp` describes --
and `ResourceOut` was chosen because it reads correctly against CASC, where
resource-outs are the expected non-success.

## Records

`ProverResult` is what an invocation returns: rich, typed, in memory.
`RunRow` is its projection onto scalars for a JSONL line, built by
`row_from_result`.

Both live in `connections`, despite `RunRow` being a persistence format. The
reason is concrete rather than principled: the `pycop` CLI has a corpus mode
(`--pattern`, `--out`) that writes JSONL itself, so the format is needed below
the line. Orchestration writes the same format rather than defining its own.

## Sharding: partition versus concurrency

Two things sound like "sharding" and only one may depend on the machine.

| | decided by | when |
|---|---|---|
| partition -- which problems are in shard 7 | the run | once, at seed time, stored with the run |
| concurrency -- how many shards this worker runs at once | the machine | every worker, every time |

A 48-core node and a laptop take different numbers of shards concurrently, but
shard 7 holds the same problems on both. Without this, a resumed run sees
different slices than the run it resumes, and shards published by a cluster
cannot be completed by a laptop.

## Packages and dependency edges

```
connections   calculus, Prover, budgets, SZS, records        -> lark
pycop         leanCoP-equivalent prover, parity              -> connections
satcop        SAT shadow, Reset                              -> connections
corpus        problem selection, sharding, artifact layout   -> connections, executor
executor      claims, atomic commits, drain, resources       -> (none)
imitation     policies, graph model, training                -> connections, corpus
```

One rule, and it is worth enforcing in CI: **`connections` never imports from a
package built on it.** A monorepo fails by letting the shared library
accumulate consumer-specific hooks until it is no longer independently usable,
and `connections` is the citable artefact here.

## Orchestration invariants

The artifact tree is the entire state of a run. Four properties make that work,
and all four are load-bearing:

1. **Completion is derivable from the tree alone** -- no database, no scheduler
   state. This is what lets a run start on a cluster and finish on a laptop.
2. **No absolute paths inside artifacts** -- so a tree can move between
   filesystems.
3. **Publication is a same-directory atomic rename** -- so a worker killed at
   any moment leaves either a finished artifact or a stray temporary.
4. **Claims expire** -- heartbeat plus timeout, so a dead node's work is
   reclaimed rather than stranded.

Given these, heterogeneous fleets need no coordination: point workers at the
same tree and let them drain.

## Open questions

- Whether `_StrategyRun` becomes public. GRPO and within-problem restarts both
  want it; nothing else does yet.
- Where `runs/download.py` and `runs/profile.py` belong. Neither is proving and
  neither is orchestration.
- Whether a learned policy trained on TPTP and evaluated on TPTP satisfies
  CASC's rule that "the precomputation and storage of information about
  individual TPTP problems or their solutions is not allowed". The evaluation
  already measures first solves made before a problem contributed training
  data, so the answer exists; it is not yet framed as a compliance argument.
