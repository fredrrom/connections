# Architecture

This repository is a uv workspace. `connections` is the library of primitives;
the packages under `packages/` build on it. This note describes the boundaries
between them.

## What is where

`connections` holds the transition system for clausal connection tableaux, the
means to act in it, and the means to run it over a corpus: states, actions,
rollouts, strategies, schedules, SZS statuses, problem selection, a bounded
parallel map over problems, and the per-problem record.

The packages under `packages/` are the things built on it. `pycop` and `satcop`
are provers -- a configuration and a CLI each. `imitation` is the experiment
layer: iterations, datasets, training, and the artifact tree that lets a
campaign survive a walltime kill and resume on another machine.

The split is by audience. Everything in `connections` is needed to prove
something and report what happened; everything in `imitation` exists only
because an experiment spans machines and days.

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

## Calculus, run, corpus

The library divides in three, each depending only on the one before it.

**`calculus/`** is the transition system: what a state is, what actions exist,
which of them the calculus admits, and what applying one does.

    rules, actions, tableau, state, dynamics

**`run/`** is acting in that system on one problem: a rollout, the strategies
that fix which system and which policy, the schedules that allocate budget
across strategies, and the SZS vocabulary for outcomes.

    rollout, strategy, status

**`corpus/`** is doing that to many problems: choosing them, running them
across a pool of processes under limits, and recording what happened.

    selection, map_problems, record, summary

`calculus` knows nothing of budgets, schedules or statuses. `run` knows nothing
of processes or of other problems. Naming this one `corpus` rather than `runs`
keeps it from reading as a plural of `run`, which is a different idea.

```
connections/
    syntax/  parsing/  clausification/  constraints/
    calculus/   rules, actions, tableau, state, dynamics
    run/        rollout, strategy, status
    corpus/     selection, map_problems, record, summary
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

`corpus.Record` is the flat per-problem line written to JSONL: an envelope of
problem, status, steps, inferences, elapsed, policy and host, plus a payload
whose contents are the attempt's own business. It is a persistence format, so
it belongs to `corpus` along with the projection that builds it from a result
and the aggregation that summarises a set of them.

An attempt produces a record. Nothing else in the orchestration layer needs to
know what either contains.

## Running many problems

`corpus.map_problems` is a bounded parallel map: it forks a pool of children,
feeds them problems, holds each to its limits, and yields records as they
finish.

```python
map_problems(problems, make_attempt, *, workers, limits) -> Iterator[Record]
```

A child that finishes sends its record back. A child that overruns is killed,
and the parent writes the record instead -- `Timeout` or `MemoryOut`, with the
elapsed time and peak RSS it measured from outside.

Problem selection is ordered and deduplicated, so two machines resolve the same
sources to the same list. How many children run at once is a property of the
machine and comes from the caller.

### What varies: the attempt

Everything above is the same whoever is calling. What differs is one function,
which runs in the child:

```python
Attempt = Callable[[ProblemRef], Record]
```

| use | what the attempt does |
|---|---|
| benchmarking a prover | `run`, and record the result |
| profiling | the same, wrapped in a profiler, with the stats in the payload |
| gathering training data | the same, with a callback that reads proof paths off closed tableaux, in the payload |

The record envelope -- problem, status, steps, elapsed, host -- is the same in
all three; only the payload differs. That is what keeps one runner serving
provers, profiling and experiments rather than three.

### Setup once, fork per problem

An attempt is built by a factory called once in the parent:

```python
make_attempt() -> Attempt
```

Whatever it loads -- a policy checkpoint, parsed axiom files -- is loaded once
and inherited by every child through copy-on-write. Forking costs about a
millisecond against the second a fresh interpreter and its imports would take,
so a child per problem is nearly free, and each starts from the same clean
snapshot rather than inheriting whatever the last problem leaked.

Inheritance runs one way. A child sees what the parent had; what the child then
changes dies with it. State reaches the next problem only by travelling back in
a record and being applied by the parent before the next fork -- a usable
channel for an online learner, and one that makes the learning signal explicit,
but not a way for a child to accumulate anything quietly.

Forking a parent that has already started threads is the hazard. After a fork
the child has only the calling thread, so a mutex another thread held at that
moment stays locked with nothing left to release it; a policy stack with OpenMP
or MKL pools running will hang its children on first allocation. Forking
through a server process started before any of it loads avoids this, but that
server has no checkpoint loaded and so gives up the sharing the fork was for.
What remains is to keep the parent single-threaded until after the fork, and to
run no inference in it, since the pools are usually created on first use.

## Experiments

`imitation` owns everything that exists only because a campaign spans machines
and days: iterations, datasets, training, and an artifact tree that survives a
walltime kill.

That tree is the campaign's whole state. A task is done when its artifact
exists, work is claimed by creating a directory, and results are published by
an atomic rename, so workers can join or die at any point without a coordinator
noticing. A task declares what it publishes and what it needs, and readiness
follows from the tree: a dataset once its shards exist, a model once its
dataset does, the next iteration's rollouts once its model does. Nothing
declares an order.

Four properties make it portable: completion is derivable from the tree alone,
no artifact contains an absolute path, publication is a same-directory rename,
and claims expire on a heartbeat so a dead node's work is reclaimed.

None of this is in `connections`, because nothing else needs it. A prover run
from a shell or a competition harness has no campaign to resume.

## Packages and dependency edges

```
connections   calculus, run, corpus, SZS                -> lark
pycop         leanCoP-equivalent prover, parity, CLI    -> connections
satcop        SAT shadow, Reset, CLI                    -> connections
imitation     policies, graph model, training, campaigns -> connections, torch
```

`connections` never imports from a package built on it. It is the citable
artefact, and it stays independently installable.

Four distributions, not six. A separate package earns its place when a second
consumer needs it: `imitation`'s artifact tree would become one if `satcop`
wanted resumable campaigns, and not before.

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
  inherit them rather than each paying the import. The parent stays
  single-threaded until after the fork, or its children deadlock.
- `prover/` splits into `calculus/` and `run/`.
- `rollout` becomes public, returning the actions it took, the state they led
  to, and why it stopped. Steps and inferences derive from the actions.
- `connections/runs/` becomes `connections/corpus/`: `run_corpus`'s pool
  becomes `map_problems`, taking limits and a worker count; `profile.py` becomes
  an attempt that profiles inside its own child rather than a wrapper around the
  runner.
- The `executor` and `corpus` packages fold away. The bounded map is
  `connections.corpus`; the artifact tree, claims and task edges belong to
  `imitation`, which is the only thing with a campaign to resume.
- learncop's `RolloutRecord` is a schedule's worth of work, not a rollout's. It
  becomes a schedule record with an entry per rollout per strategy. Deferred
  until the orchestration packages absorb that code.
- `RunRow` becomes `corpus.Record`, freeing `Attempt` for the callable that
  produces one, and gains `policy`, `payload` and `host`.

## Open questions

- Which outcome a run should report when strategies in a schedule disagree.
  The last entry's outcome currently wins, so a strategy that exhausted its
  search space is masked by a later one that ran out of steps.
- Whether a learned policy trained on TPTP and evaluated on TPTP satisfies
  CASC's rule that "the precomputation and storage of information about
  individual TPTP problems or their solutions is not allowed". The evaluation
  measures first solves made before a problem contributed training data, which
  is the substance of an answer, but it is not framed as a compliance argument.
