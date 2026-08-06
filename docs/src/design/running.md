# Running

From a policy acting in a transition system to a prover working through a
corpus. The system itself is described in [dynamics](dynamics.md).

## Vocabulary

Four concepts, from the most basic to the most assembled.

**A rollout is from a state.** A policy acts in a transition system until it
terminates or exhausts its budget.

```python
rollout(state, *, policy, step_limit=None, deadline=None) -> Rollout
```

It takes no problem, no schedule and no clausification: by the time a rollout
starts, *P(M)* exists and the state is a point in it.

A `Rollout` records the actions taken, the state they led to, and why it
stopped. Transitions are deterministic, so the action sequence and the starting
state reconstruct every intermediate state; nothing else needs storing, and
proof replay reads exactly this. Both step counts are derived from the actions
rather than counted alongside them, so they cannot disagree: a *transition step*
is one application of `T`, so the count is the number of actions; an *inference
step* is a recorded rule application, so the count is the number of actions that
appended. A prune is one transition step and removes one or more inference
steps. Budgets and reported step counts are transition steps.

The state is mutated in place. Several rollouts from one state therefore need a
copy per rollout -- cheap, because the matrix is immutable and shared and only
the tableau and constraint store are duplicated.

**A strategy fixes what to roll out in, and with what.** Its matrix options fix
the matrix and therefore *P(M)*; its policy options fix the policy. Two
strategies differing in clausification are rollouts in different transition
systems, not different runs in one.

**A schedule allocates a budget across strategies.** It divides both the steps
and the seconds it is given, by weight.

**A run turns one problem into a result.**

```python
build_state(problem_spec, *, matrix_options) -> State
run(problem_spec, *, schedule) -> Result
```

`build_state` is where a file becomes a state, and the one place `run` reaches
down to `parsing` and `clausification`: read the file, clausify it into a
matrix, wrap it as the initial state of *P(M)*. `run`
does that for each strategy in the schedule, instantiates the policy, rolls out
under that strategy's share of the budget, and stops at the first success.

## One problem, one process

`run` handles one problem, in the calling process, with no notion of memory or
of other problems. Running many is not a bigger `run`; it is many runs, and
arranging them is the caller's.

CASC needs exactly this and nothing more: systems there run "as black boxes, on
one problem at a time", with "all command line parameters ... the same for all
problems in each division", so a competition entry is one `run` per invocation
and its schedule is internal.

## Caches

Configuration is passed at the call and every cache is a local to it:

| cache | keyed by | shared across |
|---|---|---|
| matrix | problem, matrix options | the strategies of one schedule |
| parsed includes | include path | the strategies of one schedule |

*Cache lifetime equals the call.* Holding configuration as instance state
instead would cost thread-safety, a cache invalidation rule for a second call
with a different schedule, and a lifecycle, and buy almost nothing.

## Limits

| limit | divided by the schedule | enforced | reported as |
|---|---|---|---|
| steps | by weight | in the rollout, between steps | `ResourceOut` |
| time per strategy | by weight | in the rollout, between steps | `ResourceOut` |
| total time | no | by whatever ran the process | `Timeout` |
| memory | no | by whatever ran the process | `MemoryOut` |

Steps and time are checked at the same point because they fail the same way: a
step that never returns means the loop that would have noticed either limit is
never reached. Checking the clock there rather than from a signal handler costs
one read per step and avoids asking what an alarm does in the middle of a
transition.

They are inside the rollout because a schedule has to advance -- a strategy that
overran its share of the clock would leave the next strategy no turn. From
inside, steps and seconds are both an allotment that ran out, which is what
`ResourceOut` means.

Memory is outside because it drives no control flow -- there is no next strategy
to advance to when memory runs low -- and a rollout cannot measure its own
resident size, since `RLIMIT_AS` bounds address space and the two diverge once
large arenas are mapped. The total time is outside because every in-process
limit is cooperative, so only something that can kill guarantees a problem ends
-- and even that fails against an uninterruptible syscall. Nothing decides in
advance whether a step will return; the layers exist so that common failures
cost a problem rather than everything.

One number sets both the schedule's total and the outer cutoff, so the two
cannot drift: the schedule's division is an attempt at distributing it, the
cutoff is the guarantee.

Steps is the only limit that means the same thing on every machine, which is why
it is the effort measure to report. The same wall clock is a different budget on
different hardware, so a corpus run spread across node types yields a coverage
number that partly measures the cluster.

## SZS

`ResourceOut` covers a resource running out, with `Timeout` and `MemoryOut` as
the specific cases, and `GaveUp` for a system stopping of its own accord.

**A rollout** reports why it stopped: it closed the tableau, the policy ran out
of moves, or a budget was reached.

**A run** turns a schedule's rollouts into a status for the problem. The first
success wins: a proof gives `Theorem` or `Unsatisfiable`, depending on whether
the problem has a conjecture. A completely explored search space gives
`CounterSatisfiable` or `Satisfiable` -- but only from a complete strategy. A
policy with restricted backtracking has pruned its space, so exhausting what
remains says nothing about the whole, and claiming a countermodel there would be
unsound. Otherwise the result is `ResourceOut`.

**Whatever ran the process** owns `Timeout` and `MemoryOut`. Both are claims
about a process rather than a rollout, and only a watching process can make
them: its clock includes interpreter startup that no in-process timer sees, and
a rollout wedged in a C extension or killed for memory says nothing at all.

The split is by vocabulary, so the layers cannot contradict each other: a run
never says `Timeout`, a supervisor never says `ResourceOut`.

## Results

A run returns a `Result`: outcome, per-strategy results, SZS status, and
whatever a callback attached. `Result.to_dict()` makes it JSON-able, and that is
the entire data contract.

Everything else belongs to the caller. Selecting problems is `Path.glob` with
TPTP conventions. Writing records is a line of `json.dumps`, with whatever
context the runner wants to add -- host, wall time, policy version -- because
those are facts about the run rather than about the proof. Aggregating them is a
script over JSONL, and it changes with the question being asked rather than with
the prover.

## Running many problems

Nothing in `connections` does this. Each package solves it under its own
constraints, and they differ in one respect that matters.

**pycop** can pool trivially: its attempt is `run(problem, schedule)`, and both
arguments are picklable. In practice a subprocess per problem is simpler still,
because `subprocess.run(timeout=)` kills and reaps a child that will not stop,
which no worker pool does, and OOM arrives as a signal in the return code. The
command it spawns is its own CLI -- the one CASC invokes -- so there is one path
rather than two.

**imitation** cannot: its attempt holds a loaded model, which does not pickle.
Its options are a CLI of its own to spawn, or persistent workers that load once
and read problems from a pipe, replaced when one hangs. The second amortises a
one-to-two second load that the first pays per problem.

Both are threads around processes: a thread waiting on a subprocess is blocked
in `waitpid` and holds no lock, so a thread per core is enough to keep the cores
busy.

CASC permits this. Its rules handle process hierarchies -- "for systems that
create multiple processes the signal is sent first to the process at the top of
the hierarchy, then one second later to all processes" -- and in the wall-clock
divisions "no CPU time limits were imposed (so that it could be advantageous to
use all the cores on the CPU)".

## Prior art

E self-limits with a soft/hard pair, both in-process: `--soft-cpu-limit` stops
the saturation phase gracefully, `--cpu-limit` terminates "immediately ...
regardless of internal state". It treats an external limit as a scheduling
input -- "important to let E know ... so that it can adjust the schedule". C can
guarantee termination from a signal handler; Python runs handlers only between
bytecodes, which is why the hard limit here sits outside the process instead.

Vampire forks a child per strategy in portfolio mode, for parallelism, and names
the cost: forking "limits options for cooperation between proof attempts due to
reliance on inter-process communication". Any process boundary pays this. State
flows outward only, so anything one attempt learns reaches the next by being
recorded and applied, not by being left in memory.

## Composing policies

A policy is one function, `__call__(state)`. Most of the family here factors
into two independent axes:

| memory -- what `A(s, μ)` exposes | choice -- among what it exposed |
|---|---|
| none (markov) | first |
| depth-first stack | learned scorer |
| stack plus depth bound | |

leanCoP is stack-plus-bound with first-choice; the learned policies keep a
memory and replace the choice. Six classes and a multiple-inheritance diamond
collapse into three memories and a chooser supplied by whoever has one.

```python
class Memory(Protocol):
    def exposed(self, state) -> Sequence[Action]:   # A(s, μ) ⊆ A(s)
    def update(self, state, action) -> None:        # U_π
    def exhausted(self) -> ProverOutcome | None     # why nothing is left
    complete: bool                                  # does exhaustion mean anything

policy(memory, choose) -> Policy
```

`exhausted()` gives a memory somewhere to say *why* it stopped, which an empty
action list cannot. `complete` is where the soundness gate belongs: restricted
backtracking sets it false, so nothing downstream can turn its exhaustion into a
countermodel.

This is a convenience for reactive policies, not a law. A planner -- an
rlCoP-style Monte-Carlo search -- runs thousands of transitions between being
handed a state and returning an action, needing the transition function and
state copies to do it. That fits neither slot, so a planner implements
`__call__` directly and keeps its tree in its own state. `Policy` stays the only
thing that is required.
