# Architecture: what belongs where

This repository is a uv workspace. `connections` is the library; the packages
under `packages/` are built on it. This note records where the boundaries are
and, more usefully, *why* they are there, because several of them are not
obvious and were settled by argument rather than by taste.

## The line

> Everything inside one **process** is `connections`.
> Everything that spans processes is orchestration.

To CASC an ATP system *is* a process: it is invoked with a problem path, a time
limit and switches, and it prints a status. Everything that process needs is
below the line. Deciding what several processes each get -- sharding, artifact
trees, claims, resume, fleets -- is above it.

A second test, equivalent and sometimes easier to apply: **below the line
produces values, above the line persists them.** The exception that proves it
is a batch mode shipped with a prover, which writes records from inside one
process; see *Records* below.

## The system is the process; `Prover` is the top of the library

The CASC system is `pycop`'s entry point -- argument parsing, schedule
selection, SZS on stdout, exit code. `Prover` is what runs inside it: it
clausifies a problem file into an initial state, runs a schedule of strategies
under budgets, and returns a result.

`Prover` is therefore neither the system nor a primitive, and reading it as
either causes trouble. Read as the system, the CLI's responsibilities get
pulled into the library. Read as a primitive, sharding a corpus outside it
feels like a layering violation -- when in fact CASC itself shards, since the
standard division is "invoke the system once per problem".

The named provers are thin CLIs over configurations of it:

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

## Vocabulary: rollout, strategy, schedule

Three words, each meaning exactly one thing:

**A rollout is from a state.** A policy acts in a transition system from some
state until it terminates or exhausts its budget. This is the primitive, and it
is currently `_run_strategy_loop` -- private, because only the schedule has
needed it. GRPO samples several rollouts from one state; a restart is a rollout
after a `Reset`. Both want it public.

**A strategy determines what to roll out in, and with what.** Its matrix
options fix the matrix, and with it the transition system *P(M)*; its policy
options fix the policy. Two strategies differing in clausification are
therefore rollouts in *different transition systems*, not different runs in one.

**A schedule allocates a total budget across strategies.** `from_weighted`
takes total steps and seconds and divides them by weight, and `run` tries the
entries in order until one succeeds.

So `run` chooses among strategies under a budget in the same way a policy
chooses among actions under a budget -- it is a policy one level up, with a
fixed allocation rather than a learned one. Learning that allocation is the
natural next thing to want, and is where E's strategy scheduling sits.

Note that "rollout" is used more narrowly here than in the MCTS literature,
where it means the random simulation phase of a search, and more narrowly than
in learncop today, where `RolloutRecord` means the result of a whole prover run
on a problem. The narrow sense is the useful one; the others should move to it.

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

Both are one process, so both are below the line. What separates them is only
how many problems that process is handed.

## Statelessness and cache lifetime

`Prover` holds no state -- literally: no method touches an attribute, and every
`self.` in it is a call to another method. It is a module wearing a class, and
`run` and `run_multi` should be plain functions.

Configuration is passed at the call, and every cache is a local whose lifetime
is the enclosing call:

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

CASC is the strict form of the first rule. *"The first distinguished string
output is accepted as the system's result"* -- so a system that prints
`Theorem` and then crashes is credited. And a system that runs over its limit
is not assigned a status at all: *"this is noticed in the timing data, and the
system is considered to have not solved that problem."* No verdict is invented
on the system's behalf.

## Enforcement lives outside, not in `run`

`run` and `run_multi` self-limit cooperatively -- counting steps, checking a
deadline, lowering `RLIMIT_AS` where that is meaningful. They do not spawn a
subprocess to enforce their own budgets, and should not: `on_proof_found` hands
the *live* `State` to its callback, which is how proof paths are extracted, and
a process boundary would require serialising a tableau and substitution per
proof.

Hard enforcement therefore belongs to whatever invoked the process, and each
caller already has it: CASC's harness kills a system that runs over, a fleet
worker supervises a child with an RSS watchdog and a hard deadline, and on a
laptop nothing needs to.

Where a fleet does supervise, the child should persist across problems rather
than being spawned per problem -- a fresh process pays the import cost of the
policy stack every time. Process per shard, which is exactly `run_multi`'s
scope.

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
