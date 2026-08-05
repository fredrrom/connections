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
code. CASC shapes it: one problem per invocation, the same command line for
every problem in a division. Running a corpus, writing records and summarising
them are not part of it -- those belong to orchestration, so a prover CLI has
no reason to depend on `corpus` or `executor`.

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
rollout(state, *, policy, step_limit=None, deadline=None) -> Rollout
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

**A run turns one problem into a result.** It builds the matrix for each
strategy in the schedule, instantiates the policy, rolls out under that
strategy's share of the steps and the clock, and stops at the first success. It owns the
caches and maps outcomes to SZS statuses.

```python
run(problem, *, schedule) -> Result
```

A run chooses among strategies under a budget much as a policy chooses among
actions under a budget -- a policy one level up, with a fixed allocation rather
than a learned one.

## `run` is one problem

```python
run(problem, *, schedule) -> Result
```

One problem, in the calling process, with no notion of memory or of other
problems. It builds the matrix for each strategy in the schedule, instantiates
the policy, rolls out under that strategy's share of the steps and the clock,
and stops at the first success.

Running many problems is not a bigger `run`; it is many runs, and arranging
them is orchestration's job. That separation is what lets a hung problem cost
one problem: a soft limit is cooperative and a search wedged in a C extension
will ignore it, so the only way to guarantee that every problem is attempted is
to give each one a process that can be killed.

CASC needs exactly this shape and nothing more. Systems there run "as black
boxes, on one problem at a time", with "all command line parameters ... the
same for all problems in each division", so a competition entry is one `run`
per invocation and its schedule is internal.

CASC used to have a division shaped like a corpus run. The Large Theory Batch
division passed a batch specification file and explicitly permitted training
and memorisation across the batch, which made it the natural home for learned
provers. It has gone on hiatus, so no current division sanctions learning from
the competition corpus.

## Caches

`run` is a function, not a method on an object. Configuration is passed at the
call, and every cache is a local to it:

| cache | keyed by | shared across |
|---|---|---|
| matrix | problem, matrix options | the strategies of one schedule |
| parsed includes | include path | the strategies of one schedule |

*Cache lifetime equals the call.* Holding configuration as instance state
instead would buy little and cost thread-safety, a cache invalidation rule for a
second call with a different schedule, and a lifecycle.

Sharing anything across problems is orchestration's business, and it has a
better mechanism than a cache: a parent that loads the policy and parses shared
axioms once, then forks a child per problem. Each child inherits the loaded
state through copy-on-write, so the cost is paid once without any problem being
able to corrupt the next one's.

## Budgets

Three limits, and they are three different kinds of thing.

**Steps bound a rollout.** A step is one transition, so a step limit is a
property of the rollout and nothing else -- `rollout` counts them and stops.
It is the only limit that means the same thing on every machine, which is why
it is the effort measure to report.

**Time bounds a strategy's turn.** It is spendable and divisible: a schedule
divides the total it was given by weight, so each strategy gets a share of the
clock alongside its share of the steps. Unlike steps it is not portable -- the
same limit is a different budget on different hardware -- so a corpus run
spread across node types yields a coverage number that partly measures the
cluster, and records carry the host to make a `Timeout` interpretable.

**Memory is a ceiling on the process.** It is not spendable and cannot be
divided across strategies.

Steps and time both bound a rollout, and whichever binds first stops it. Both
are divided by the schedule, and a strategy that overran its share of the clock
would leave the next strategy no turn -- so a rollout has to notice its own
deadline, exactly as it notices its own step limit. Stopping on either produces
a result: what was tried, how far it got, and why it stopped.

Memory is different. It drives no control flow -- there is no next strategy to
advance to when memory runs low -- and a search cannot measure its own resident
size reliably. It belongs entirely to whatever runs the process.

The total time for a problem also belongs outside. A rollout stopping at its
share is cooperative and can fail; only a parent that can kill guarantees the
problem ends at all.

Cores, nodes and concurrency are not budgets. They change how fast the same
work happens, not what the search does, and belong to orchestration.

## SZS: who reports what

SZS is the output contract. `ResourceOut` covers a resource running out, with
`Timeout` and `MemoryOut` as the specific cases, and `GaveUp` for a system
stopping of its own accord.

**A rollout** reports why it stopped: it closed the tableau, the policy ran out
of moves, or the step limit was reached.

**A run** turns a schedule's rollouts into a status for the problem. A proof
gives `Theorem` or `Unsatisfiable`, depending on whether the problem has a
conjecture. A completely explored search space gives `CounterSatisfiable` or
`Satisfiable`. Exhausting the steps gives `ResourceOut`, and exhausting the
clock gives `Timeout` -- a run observes both, because both bound its rollouts.

**Whatever runs the process** owns `MemoryOut`, and owns `Timeout` in the case
a run cannot report: the one where it never stopped. A search wedged in a C
loop cannot fire its own alarm, and a process killed for memory reports nothing
at all. A parent watching a child also measures both faithfully, including
interpreter startup, which no in-process clock can see.

Neither carries weight in competition -- CASC scores Success statuses, and a
printed `Timeout` scores the same as being killed. They exist for the
experiment records, where telling a hard problem from a slow node is the whole
point.

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

One thing carries over directly: **a time budget is an input to scheduling**,
not only a ceiling. A schedule can divide a total only if it is told one, which
is why a total may be passed in even though nothing in `connections` enforces
it.

Two things do not. There is no competitive value in a self-reported resource
status -- CASC scores Success statuses, so a system that prints `ResourceOut`
and one killed by the harness have both failed to solve the problem, and E
prints it for the reader rather than the scoreboard. And E's reason for keeping
enforcement inside does not transfer: C can guarantee termination from a signal
handler, while Python runs handlers only between bytecodes, so a tight loop in
an extension ignores an alarm indefinitely.

That is the case for one process per problem: a cooperative limit cannot
guarantee that a problem ends, so the guarantee has to come from a parent that
can kill. It is not a case for removing the clock from the search. E's soft
limit exists so the prover can stop and say what it found, and a schedule needs
the same thing for a different reason -- a strategy that ignores its share of
the clock leaves the next strategy no turn.

Vampire's cost applies to us as well. Forking per problem rules out sharing
anything discovered in one attempt with the next, which is exactly what a
learned prover would want. The parent can share in one direction -- loading the
policy and parsing shared axioms before forking, so children inherit them
through copy-on-write -- but nothing flows back except the record.

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

A shard is a task; each problem in it is a process:

```python
TaskSpec(
    key=f"shard_{i:05d}",
    target=root / "shards" / f"shard_{i:05d}.jsonl",
    run=lambda: write_rows(attempt_each(shard.problems, schedule=...)),
)
```

`attempt_each` loads the policy once, then forks a child per problem which
calls `connections.run`. The parent holds each child to the wall clock and
memory limit, kills it if it exceeds them, and records `Timeout` or
`MemoryOut`; a child that finishes reports its own result. `corpus` writes the
rows, `executor` decides who runs the shard and publishes it atomically, and a
summary task declares the shards as `needs` so it runs once they are present.

The shard is the unit of scheduling and the problem is the unit of isolation. A
shard that dies costs a shard's work, and only because a worker died; a problem
that hangs costs one problem.

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

- `class Prover` goes; `run` becomes a module-level function over one problem.
- A rollout stops on its step limit or its deadline, whichever binds first, so
  a schedule can advance between strategies.
- Memory and the guarantee that a problem ends at all leave `connections`. A
  parent forks a child per problem, holds it to the total, and reports
  `MemoryOut` and the `Timeout` a hung search could not report itself.
- The policy and any shared axioms are loaded in that parent, so children
  inherit them rather than each paying the import.
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
  individual TPTP problems or their solutions is not allowed". The LTB division
  used to permit exactly this and is on hiatus, so there is currently no
  division that sanctions training on the competition corpus. The evaluation
  measures first solves made before a problem contributed training data, which
  is the substance of an answer, but it is not framed as a compliance argument.
