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
one problem: a soft limit is cooperative and a rollout wedged in a C extension
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

## Limits

| limit | divided by the schedule | enforced | reported as |
|---|---|---|---|
| steps | by weight | in the rollout, between steps | `ResourceOut` |
| time per strategy | by weight | in the rollout, between steps | `ResourceOut` |
| total time | no | by the parent, which can kill | `Timeout` |
| memory | no | by the parent | `MemoryOut` |

Steps and time are checked at the same point because they fail the same way: a
step that never returns means the loop that would have noticed either limit is
never reached. Checking the clock there rather than from a signal handler costs
one read per step and avoids asking what an alarm does in the middle of a
transition.

They are inside the rollout because a schedule has to advance -- a strategy that
overran its share of the clock would leave the next strategy no turn. From
inside, steps and seconds are both an allotment that ran out, which is what
`ResourceOut` means.

Memory is outside because it drives no control flow: there is no next strategy
to advance to when memory runs low, and a rollout cannot measure its own
resident size, since `RLIMIT_AS` bounds address space and the two diverge
sharply once large arenas are mapped. The total time is outside because every
in-process limit is cooperative -- only a parent that can kill guarantees a
problem ends, and even that fails against an uninterruptible syscall. Nothing
here decides in advance whether a step returns; the layers exist so that the
common failures cost a problem rather than a shard.

`Timeout` is a claim about a process rather than a rollout, and only a watching
process can make it, since its clock includes interpreter startup that no
in-process timer sees. The split is therefore by vocabulary and the layers
cannot contradict each other: a run never says `Timeout`, a parent never says
`ResourceOut`. Where they could overlap -- a run that finished just as a limit
expired -- the rule is **refine, never overwrite**, which is also how CASC reads
output: *"the first distinguished string output is accepted as the system's
result"*, and a system that runs over is not credited rather than assigned a
status.

Steps is the only limit that means the same thing on every machine, and is the
effort measure to report. The same wall clock is a different budget on
different hardware, so a corpus run spread across node types yields a coverage
number that partly measures the cluster. Records carry the host to make a
`Timeout` interpretable, and both clocks, because they answer different
questions: time summed across strategies is the cost of the rollouts, the
parent's wall time is the cost of the process.

Cores, nodes and concurrency are not limits in this sense. They change how fast
the same work happens, not what the rollouts do.

### Prior art

E self-limits with a soft/hard pair, both in-process: `--soft-cpu-limit` stops
the saturation phase gracefully, `--cpu-limit` terminates "immediately ...
regardless of internal state". It also treats an external limit as a scheduling
input -- *"important to let E know ... so that it can adjust the schedule"*. C
can guarantee termination from a signal handler; Python runs handlers only
between bytecodes, which is why the hard limit here moves outside instead.

Vampire forks a child per strategy in portfolio mode, for parallelism, and
names the cost: forking "limits options for cooperation between proof attempts
due to reliance on inter-process communication". Forking per problem pays the
same cost. A parent can share downward -- loading the policy and parsing shared
axioms before forking, so children inherit them -- but nothing flows back
except the record.

Neither prover gains anything competitive from self-reporting a resource
status. CASC scores Success statuses, so a printed `ResourceOut` and a harness
kill are the same result; E prints it for the reader. These statuses earn their
place in the experiment records, where telling a hard problem from a slow node
is the point.

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
  a schedule can advance between strategies. Both are checked between steps,
  which removes the wall-clock alarm and the exception it raised.
- `Timeout` and `MemoryOut` leave `connections` entirely; a run reports
  `ResourceOut` whichever of its budgets ran out. A parent forks a child per
  problem, holds it to the total, and owns those two statuses.
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
