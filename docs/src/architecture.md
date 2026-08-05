# Architecture

This repository is a uv workspace. `connections` is the library of primitives;
the packages under `packages/` build on it. This note describes the boundaries
between them.

## Two layers

`connections` holds the transition system for clausal connection tableaux and
the means to act in it: states, actions, rollouts, strategies, schedules, and
the SZS vocabulary for outcomes. It returns values and writes nothing to disk.

The orchestration packages run many such processes over a corpus. They select
and shard problems, lay out an artifact tree, claim work between competing
workers, publish results atomically, and resume an interrupted run. They
persist what `connections` returns.

The two are separated by the process boundary. A CASC invocation -- a problem
path, a time limit, a status on stdout -- uses `connections` and none of the
orchestration packages; a fleet draining a corpus uses both. New code belongs
in `connections` if a single invocation needs it, and in orchestration if it
exists only because several processes are running.

## Primitives, not a prover

`connections` provides the primitives a prover is assembled from. The named
provers are the CLIs that assemble them:

| | |
|---|---|
| `pycop` | leanCoP strategies + a CLI |
| `ilcop` | intuitionistic configuration |
| `satcop` | SAT shadow and `Reset` |

A CLI owns argument parsing, schedule selection, SZS on stdout and the exit
code. It is shaped by CASC: one problem per invocation in the standard
division, a batch specification in LTB. Running a corpus, writing records and
summarising them are not part of it -- those belong to orchestration, so a
prover CLI has no reason to depend on `corpus` or `executor`.

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

## Run vocabulary

Four concepts, from the most basic to the most assembled.

**A rollout is from a state.** A policy acts in a transition system from some
state until it terminates or exhausts its budget.

```python
rollout(state, *, policy, step_limit=None) -> Rollout
```

It takes no problem, no schedule and no clausification: by the time a rollout
starts, *P(M)* exists and the state is a point in it.

A `Rollout` records the actions taken, the state they led to, and why it
stopped. Transitions are deterministic, so the action sequence and the starting
state reconstruct every intermediate state; nothing else needs storing, and
proof replay reads exactly this.

    actions      the trajectory, in order
    final_state  what the actions led to
    outcome      why it stopped, if it stopped for a reason

Steps and inferences are derived from the actions rather than counted
alongside them, so they cannot disagree: steps is the number of actions, and
inferences the number that applied a rule. An undo is a step but not an
inference.

Because it takes a state and returns one, rollouts compose: several can start
from the same state to compare what different policies do with it, and one can
continue from where another stopped.

**A strategy fixes what to roll out in, and with what.** Its matrix options fix
the matrix and therefore the transition system *P(M)*; its policy options fix
the policy. Two strategies differing in clausification are rollouts in
different transition systems, not different runs in one.

**A schedule allocates a total budget across strategies.** `from_weighted`
takes total steps and seconds and divides them by weight.

**A run turns problems into results.** It builds the matrix for each strategy in
the schedule, instantiates the policy, rolls out under that strategy's share of
the budget, and stops at the first success. It owns the caches and maps
outcomes to SZS statuses.

```python
run(problems, schedule=...) -> Iterator[Result]
```

`problems` is one problem or many; the result is always an iterator, so the
caller's shape does not change with the corpus size. A single-problem
invocation reads `result, = run(problem, schedule=...)`.

A run chooses among strategies under a budget much as a policy chooses among
actions under a budget -- a policy one level up, with a fixed allocation rather
than a learned one.

## Two invocation shapes

CASC defines two, and one `run` covers both. The standard division passes a
problem path per invocation; the Large Theory Batch division passes a batch
specification file and permits training and memorisation across the batch.
Learning work is LTB-shaped, which is what makes caching across problems
legitimate.

Both are one process. They differ only in how many problems that process is
handed, which is the argument to `run`.

## Cache lifetime

`run` is a function, not a method on an object. Configuration is passed at the
call, and every cache is a local to it:

| cache | keyed by | shared across |
|---|---|---|
| matrix | problem, matrix options | the strategies of one schedule |
| parsed includes | include path | the problems of one call |
| loaded policy | policy options | the problems of one call |

*Cache lifetime equals the call.* Holding configuration as instance state
instead would save a model reload between calls -- about a second against a
shard of minutes -- at the cost of thread-safety, a cache invalidation rule for
a second call with a different schedule, and a lifecycle.

The matrix cache spans the whole call, but a problem is attempted once per
configuration within a corpus run, so what it actually shares is the strategies
of one schedule.

## Budgets

Three limits, and they are three different kinds of thing.

**Steps bound a rollout.** A step is one transition, so a step limit is a
property of the rollout and nothing else -- `rollout` counts them and stops.
It is the only limit that means the same thing on every machine, which is why
it is the effort measure to report.

**Time bounds a strategy's turn.** It is spendable and divisible: the schedule
takes the total the process was given and divides it by weight, so each
strategy gets a share of the clock alongside its share of the steps. Unlike
steps it is not portable -- the same limit is a different budget on different
hardware -- so a corpus run spread across node types yields a coverage number
that partly measures the cluster, and records carry the host to make a
`Timeout` interpretable.

**Memory is a ceiling on the process.** It is not spendable and cannot be
divided across strategies; it holds for the duration of the call.

Steps are enforced by the rollout that counts them. Time and memory are
enforced twice, softly inside the search and firmly outside it; see *Where each
limit is enforced*.

Cores, nodes and concurrency are not budgets. They change how fast the same
work happens, not what the search does, and belong to orchestration.

## SZS: who reports what

SZS is the output contract. `ResourceOut` covers a resource running out, with
`Timeout` and `MemoryOut` as the specific cases, and `GaveUp` for a system
stopping of its own accord.

Three layers, each reporting only what it can observe.

**A rollout** reports why it stopped: it closed the tableau, the policy ran out
of moves, or the step limit was reached.

**A schedule's worth of rollouts** becomes a status for the problem. A proof
gives `Theorem` or `Unsatisfiable`, depending on whether the problem has a
conjecture. A completely explored search space gives `CounterSatisfiable` or
`Satisfiable`. Finishing the schedule with no proof and no steps left gives
`ResourceOut` -- the step budget is the only resource visible from inside the
search.

**Whatever holds the process to its limits** owns `Timeout` and `MemoryOut`. A
search that gave up on a problem within its soft limit reports them itself; a
search that was killed cannot, since a wedged process cannot fire its own alarm
and a process killed for memory reports nothing at all.

These two statuses carry no weight in competition -- CASC scores Success
statuses, and a printed `Timeout` scores the same as being killed. They exist
for the experiment records, where telling a hard problem from a slow node is
the whole point.

The rule running through them: **refine, never overwrite.** A layer speaks only
when the one below produced nothing. A search that returned `Theorem` before a
limit fired returned `Theorem`. CASC applies this strictly -- *"the first
distinguished string output is accepted as the system's result"* -- and a
system that runs over its limit is not credited rather than assigned a status.

`StepBudget` maps to `ResourceOut` rather than `GaveUp`, which reads correctly
against CASC where resource-outs are the expected non-success.

## Limits: what established provers do

E self-limits in-process with a soft/hard pair. `--soft-cpu-limit` (290s by
default) stops the saturation phase gracefully, so the prover can post-process
and print what it has; `--cpu-limit` (300s) terminates "immediately after
reaching the time limit, regardless of internal state". Memory goes through
`setrlimit()`, and the manual concedes it "may not work everywhere". E also
takes the external limit as an input rather than only a constraint: *"if you
impose a different one externally, it is important to let E know via the
`--cpu-limit=XXX` option so that it can adjust the schedule."*

Vampire forks a child per strategy in portfolio mode, which is what its CASC
mode runs. The motivation there is parallelism rather than measurement, and the
cost is explicit: forking "limits options for cooperation between proof
attempts due to reliance on inter-process communication".

Two things carry over. **The time budget is an input to scheduling**, not just a
ceiling -- a schedule can only divide a total it knows. And **soft and hard
limits do different jobs**: the soft one lets a search abandon what it is doing
and move on, the hard one guarantees it stops at all.

What does not carry over is any competitive value in self-reported resource
statuses. CASC scores Success statuses; a system that prints `ResourceOut` and
one that is killed by the harness have both failed to solve the problem. E
prints it for the reader, not for the scoreboard.

Self-limiting still matters, for control flow rather than reporting, and it
follows from how many problems a process is given.

A shard is fifty problems in one process, because starting one costs the import
of the policy stack and doing that fifty times is waste. If the first problem
is unsolvable and nothing stops the search, the other forty-nine are never
attempted. Only the process can make that call: an outside killer would have to
end the whole shard to end one problem. So a process handling many problems
must bound each one itself.

The standard division inverts this. One problem, one process, and being killed
is a perfectly good ending because there is nothing queued behind it. LTB has
the shard's shape instead -- a batch, a wall-clock limit per problem, and an
overall limit -- and the per-problem limit is the system's to honour.

## Where each limit is enforced

The soft limits stay in the search, because the search is what has to give up
on one problem and start the next:

```python
for problem in problems:
    for entry in schedule.entries:
        with wall_clock(entry.timeout_seconds):     # this strategy's share
            rollout(state, policy=..., step_limit=entry.step_limit)
```

The hard limits sit outside it. E can keep both inside because C can guarantee
termination from a signal handler; Python cannot, since handlers run only
between bytecodes and a tight loop in a C extension will not yield. The same
argument applies to measurement:

- Startup is invisible from inside. Interpreter start, imports and module init
  all precede any in-process timer, and with a policy stack loaded that is
  seconds.
- `RLIMIT_AS` bounds address space rather than resident size, and the two
  diverge sharply once large arenas are mapped.
- A process killed for memory reports nothing. `ru_maxrss` is readable only by
  a process that survived.

So `Timeout` and `MemoryOut` are verdicts of whatever holds the process to its
demands, and the outer limits are derived from the inner ones so the two cannot
drift apart:

```python
hard_deadline_seconds = 1.5 * timeout_seconds + 60
```

If the outer limit fires, the inner one was not respected: a hang rather than a
slow problem, recorded as an error rather than a `Timeout`.

Two clocks result, and a record can carry both. Time summed across strategies
is the cost of the search, which is what comparing policies wants. Wall time
measured from outside is the cost of the process, includes startup, and is what
the limit is enforced against.

## Records

A run returns a rich, typed result in memory: outcome, per-strategy results,
SZS status, and any proof payload a callback attached. `connections` produces
these and stops there.

The flat per-problem record written to a JSONL line -- problem, status, steps,
inferences, elapsed, policy, host -- is a persistence format, and belongs to
`corpus` along with the projection that builds it from a result and the
aggregation that summarises a set of them.

## Orchestration

Two packages sit above `connections`. Neither knows what a prover is.

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

A shard is a task whose body is one `run` call:

```python
TaskSpec(
    key=f"shard_{i:05d}",
    target=root / "shards" / f"shard_{i:05d}.jsonl",
    run=lambda: write_rows(run(shard.problems, schedule=...)),
)
```

`run` yields records, `corpus` writes them, `executor` decides who runs the
shard and publishes the result atomically. A summary task declares the shards
as `needs`, so it runs once they are all present.

This is why `run` yields rather than writes, and why its caches are scoped to
the call: one call is one shard on one worker.

## Packages and dependency edges

```
connections   calculus, run, budgets, SZS                    -> lark
pycop         leanCoP-equivalent prover, parity, CLI          -> connections
satcop        SAT shadow, Reset, CLI                          -> connections
executor      claims, atomic commits, drain, resources        -> (none)
corpus        selection, sharding, records, benchmark fetch   -> connections, executor
imitation     policies, graph model, training                 -> connections, corpus
```

`connections` never imports from a package built on it. It is the citable
artefact, and it stays independently installable.

## Decided, not yet done

The code lags this document on one surface. These should land together:

- `class Prover` goes; `run` becomes a module-level function taking one problem
  or many, always yielding results.
- Time and memory are enforced twice: soft limits inside the search so it can
  stop and report, hard limits outside it so termination is guaranteed and the
  numbers are measured faithfully.
- `prover/` splits into `calculus/` and `run/`.
- `rollout` becomes public, returning the actions it took, the state they led
  to, and why it stopped. Steps and inferences derive from the actions.
- `connections/runs/` dissolves: the problem loop folds into `run`, the
  record format and summaries move to `corpus`, and corpus fetching and
  profiling go with them.
- `pycop` loses its corpus mode; benchmarking a corpus is a `corpus` entry
  point that takes a prover, and benchmark fetching becomes another.
- learncop's `RolloutRecord` is a schedule's worth of work, not a rollout's. It
  becomes a schedule record with an entry per rollout per strategy. Deferred
  until the orchestration packages absorb that code.
- `corpus.Attempt` absorbs the record fields it lacks: `inference_actions`,
  `strategy_count`, `winning_strategy_index`, and `host`.

## Open questions

- Which outcome a run should report when strategies in a schedule disagree.
  The last entry's outcome currently wins, so a strategy that exhausted its
  search space is masked by a later one that ran out of steps.
- Whether a learned policy trained on TPTP and evaluated on TPTP satisfies
  CASC's rule that "the precomputation and storage of information about
  individual TPTP problems or their solutions is not allowed". The evaluation
  measures first solves made before a problem contributed training data, which
  is the substance of an answer, but it is not framed as a compliance argument.
