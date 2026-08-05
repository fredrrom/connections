# Architecture

This repository is a uv workspace. `connections` is the library of primitives;
the packages under `packages/` build on it. This note describes the boundaries
between them.

## The line

> Everything inside one **process** is `connections`.
> Everything that spans processes is orchestration.

To CASC an ATP system is a process: it is invoked with a problem path, a time
limit and switches, and it prints a status. Everything that process needs is
below the line. Deciding what several processes each get -- sharding, artifact
trees, claims, resume, fleets -- is above it.

An equivalent test, often easier to apply: **below the line produces values,
above the line persists them.** The one exception is a batch mode shipped with
a prover, which writes records from inside a single process; see *Records*.

## Primitives, not a prover

`connections` provides the primitives a prover is assembled from. The named
provers are the CLIs that assemble them:

| | |
|---|---|
| `pycop` | leanCoP strategies + a CLI |
| `ilcop` | intuitionistic configuration |
| `satcop` | SAT shadow and `Reset` |

A CLI owns argument parsing, schedule selection, SZS on stdout and the exit
code. None of that belongs in the library.

## Calculus and run

The primitives divide in two.

**`calculus/`** is the transition system: what a state is, what actions exist,
which of them the calculus admits, and what applying one does.

    rules, actions, tableau, state, dynamics

**`run/`** is acting in that system: a rollout, the strategies that fix which
system and which policy, the schedules that allocate budget across strategies,
and the SZS vocabulary for reporting outcomes.

    rollout, strategy, status

The dependency runs one way. `calculus` knows nothing of budgets, schedules or
statuses; `run` is the only thing that connects a policy to a transition
system.

```
connections/
    syntax/  parsing/  clausification/  constraints/
    calculus/   rules, actions, tableau, state, dynamics
    run/        rollout, strategy, status
    policy/
```

## Vocabulary

**A rollout is from a state.** A policy acts in a transition system from some
state until it terminates or exhausts its budget.

```python
rollout(state, *, policy, step_limit=None) -> Rollout   # steps, inferences, outcome
```

It takes no problem, no schedule and no clausification: by the time a rollout
starts, *P(M)* exists and the state is a point in it. The state is mutated in
place rather than copied, so a caller can inspect the closed tableau
afterwards, which is what proof replay reads.

This is the composable unit. GRPO samples several rollouts from one state; a
restart is a rollout after a `Reset`.

**A strategy fixes what to roll out in, and with what.** Its matrix options fix
the matrix and therefore the transition system *P(M)*; its policy options fix
the policy. Two strategies differing in clausification are rollouts in
different transition systems, not different runs in one.

**A schedule allocates a total budget across strategies.** `from_weighted`
takes total steps and seconds and divides them by weight; `run` tries the
entries in order until one succeeds.

`run` therefore chooses among strategies under a budget much as a policy
chooses among actions under a budget -- a policy one level up, with a fixed
allocation rather than a learned one.

Elsewhere "rollout" is broader: in the MCTS literature it is the random
simulation phase of a search, and in learncop a `RolloutRecord` is the result
of a whole prover run on a problem. Here it always means a policy acting from
a state.

## Two invocation shapes

```python
run(problem, schedule=...)         # one problem
run_multi(problems, schedule=...)  # a batch, one process
```

These match CASC's two invocation modes. The standard division passes a problem
path per invocation; the Large Theory Batch division passes a batch
specification file and permits training and memorisation across the batch.
Learning work is LTB-shaped, which is what makes caching across problems
legitimate in `run_multi`.

Both are one process, so both are below the line. They differ only in how many
problems that process is handed.

## Cache lifetime

`run` and `run_multi` are functions. Configuration is passed at the call, and
every cache is a local whose lifetime is the enclosing call:

| cache | lives in | shared across |
|---|---|---|
| matrix | `run` | the strategies of one schedule |
| parsed includes | `run_multi` | the problems of one batch |
| loaded policy | `run_multi` | the problems of one batch |

*Cache lifetime equals the enclosing call.* Holding configuration as instance
state instead would save a model reload between shards -- about a second
against a shard of minutes -- at the cost of thread-safety, a cache
invalidation rule for a second call with a different schedule, and a lifecycle.

The matrix cache is keyed by problem and matrix options, so it could be lifted
across problems, but within a corpus run each problem is attempted once per
configuration and a wider cache would only miss. The sharing that pays is
across the strategies of a schedule.

## Budgets are semantic; allocation is not

Steps, memory and time change what the search does, so they belong below the
line. Cores, nodes and concurrency change only how fast the same work happens,
so they belong to orchestration.

The three budgets differ in kind:

| budget | portable across machines | enforceable in-process |
|---|---|---|
| steps | yes | yes |
| memory | yes | only via `RLIMIT_AS`, which is unreliable when a large virtual mapping (torch) dwarfs RSS, and a no-op on macOS |
| time | **no** | yes |

Steps is the only one that is both, and is therefore the effort measure to
report. A wall-clock limit is a different budget on different hardware, so a
corpus run spread across node types yields a coverage number that partly
measures the cluster. Records carry the host so a `Timeout` can be interpreted.

### Nested limits

A runner sets its own limits outside the process's, derived from them so the
two cannot drift apart:

```python
hard_deadline_seconds = 1.5 * timeout_seconds + 60
```

The inner limit is semantic: the process notices it and reports a status. The
outer limit is operational: if it fires, the inner one was not respected, which
is a hang rather than a slow problem, and is recorded as an error.

## SZS: who reports what

SZS is the output contract. `ResourceOut` covers a resource running out, with
`Timeout` and `MemoryOut` as the specific cases, and `GaveUp` for a system
stopping of its own accord.

Responsibility follows from who is still running:

- The process reports what it observes: a proof, an exhausted search space, its
  own step budget (`ResourceOut`), its own wall clock (`Timeout`), its own
  memory cap (`MemoryOut`), internal errors.
- The runner reports only when the process died without producing a status.
  It usually cannot know why, so it records an error status with the evidence
  -- signal, elapsed time, peak RSS -- rather than a guess.

The runner refines, never overwrites: a process that returned `Theorem` before
a watchdog fired returned `Theorem`. CASC applies the same rule strictly, since
*"the first distinguished string output is accepted as the system's result"*,
and a system that runs over its limit is not credited rather than assigned a
status.

`StepBudget` maps to `ResourceOut` rather than `GaveUp`, which reads correctly
against CASC where resource-outs are the expected non-success.

## Enforcement

`run` and `run_multi` self-limit cooperatively: counting steps, checking a
deadline, lowering `RLIMIT_AS` where that is meaningful. They do not spawn a
subprocess to enforce their own budgets, because `on_proof_found` hands the
live `State` to its callback and a process boundary would mean serialising a
tableau and substitution per proof.

Hard enforcement belongs to whatever invoked the process: CASC's harness kills
a system that runs over, a fleet worker supervises a child with an RSS watchdog
and a hard deadline, and a laptop needs neither. Where a fleet supervises, the
child persists across problems rather than being spawned per problem, so the
import cost of the policy stack is paid once. Process per shard, which is
`run_multi`'s scope.

## Records

A run returns a rich, typed result in memory. `RunRow` is its projection onto
scalars for a JSONL line, built by `row_from_result`.

Both live in `connections`, despite `RunRow` being a persistence format,
because the `pycop` CLI has a corpus mode (`--pattern`, `--out`) that writes
JSONL itself. Orchestration writes the same format rather than defining its
own.

## Orchestration

Two packages sit above the line. Neither knows what a prover is.

### `executor`: running work without a coordinator

The artifact tree is the entire state of a run. A task is done when its target
exists, work is claimed by creating a directory, and results are published by
an atomic rename. Nothing else holds authoritative state, so workers can join
or die at any point.

```python
TaskSpec(key=..., target=..., needs=(...), run=...)
run_plan(tasks, worker_id="w0")
```

A task declares the artifact it publishes and the artifacts it needs. Readiness
follows from the tree -- a task runs once its inputs exist and its own target
does not -- so nothing declares an order and there are no stage barriers. The
task set is a callable rather than a list, re-evaluated each pass, so work can
appear mid-run: iteration *k+1*'s tasks exist once *k*'s model lands.

Four properties make the tree portable:

1. Completion is derivable from the tree alone -- no database, no scheduler
   state. A run can start on a cluster and finish on a laptop.
2. No absolute paths inside artifacts.
3. Publication is a same-directory atomic rename, so a killed worker leaves
   either a finished artifact or a stray temporary.
4. Claims expire on a heartbeat timeout, so a dead node's work is reclaimed.

### `corpus`: what to run, and where it lands

Problem selection is ordered and deduplicated, so two machines resolve the same
sources to the same list. Sharding is a deterministic partition of that list:
shard 7 holds the same problems everywhere, which is what lets a killed worker
be replaced and a run be resumed.

Shard membership is a property of the run, fixed when it is seeded. How many
shards a worker takes concurrently is a property of the machine. Only the
second varies with hardware.

### How they compose

A shard is a task whose body is one `run_multi` call:

```python
TaskSpec(
    key=f"shard_{i:05d}",
    target=root / "shards" / f"shard_{i:05d}.jsonl",
    run=lambda: write_rows(run_multi(shard.problems, schedule=...)),
)
```

`run_multi` yields records, `corpus` writes them, `executor` decides who runs
the shard and publishes the result atomically. A summary task declares the
shards as `needs`, so it runs once they are all present.

This is why `run_multi` yields rather than writes, and why its caches are
call-scoped: one call is one shard on one worker.

## Packages and dependency edges

```
connections   calculus, run, budgets, SZS, records            -> lark
pycop         leanCoP-equivalent prover, parity               -> connections
satcop        SAT shadow, Reset                               -> connections
corpus        problem selection, sharding, artifact layout    -> connections, executor
executor      claims, atomic commits, drain, resources        -> (none)
imitation     policies, graph model, training                 -> connections, corpus
```

`connections` never imports from a package built on it. It is the citable
artefact, and it stays independently installable.

## Decided, not yet done

The code lags this document on one surface. These should land together:

- `class Prover` goes; `run` and `run_multi` become module-level functions.
- `prover/` splits into `calculus/` and `run/`.
- `rollout` becomes public.
- `run_multi` is added, with include and policy caches local to the call.
- `corpus.Attempt` folds into `RunRow`, which gains `policy`, `payload` and
  `host`.

## Open questions

- Where `runs/download.py` and `runs/profile.py` belong. Neither is proving and
  neither is orchestration.
- Whether a learned policy trained on TPTP and evaluated on TPTP satisfies
  CASC's rule that "the precomputation and storage of information about
  individual TPTP problems or their solutions is not allowed". The evaluation
  measures first solves made before a problem contributed training data, which
  is the substance of an answer, but it is not framed as a compliance argument.
