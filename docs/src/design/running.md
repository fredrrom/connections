# Running

From an agent acting in a transition system to a prover working through a
corpus. The system itself is described in [dynamics](dynamics.md); an agent
implements a policy, and the code says Agent where the paper says pi.

## Vocabulary

Four concepts, from the most basic to the most assembled.

**A rollout is from a state.** An agent acts in a transition system until it
offers nothing or exhausts its budget.

```python
rollout(state, agent, *, step_limit=None, deadline=None, record=True) -> Rollout
```

The rollout is the bare agent-environment loop, and it never reads the
tableau: closure is the agent's to observe through the percept and the judge's
to verify afterwards, so the loop is generic over states. `Stop` is the
rollout's own observation -- `AGENT_DONE`, `STEP_BUDGET`, `TIME_BUDGET` -- and
`AGENT_DONE` is the only stop that consults the agent, recording its
`AgentStatus` once.

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
copy per rollout -- not too expensive, because the matrix is immutable and shared
and only the tableau and constraint store are duplicated.

**A strategy fixes what to roll out in, and with what.** Its matrix options fix
the matrix and therefore *P(M)*; its agent options fix the agent. Two
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
does that for each strategy in the schedule, rolls the agent out under that
strategy's share of the budget, and stops at the first success. Agent lifetime
is the caller's choice: by default each entry instantiates a fresh agent from
its options, the frozen-theta protocol, while `run(..., agent=)` reuses one
agent across entries -- the deliberate exception for intra-conjecture work.
Verdicts aggregate by strength: a proof stops the schedule, and a systematic
strategy's exhaustion is never overwritten by a later pruned strategy's giving
up.

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

**An agent** speaks only about itself, in `AgentStatus`: `CLOSED`,
`DFS_EXHAUSTED`, `ID_FIXED_POINT`, `GAVE_UP`. AgentStatus is a plain
enum; the judge in `run` holds the one map from statuses to outcomes, and
statuses absent from the map carry no claim. `GAVE_UP` is the default when an agent offers nothing and claims
nothing, so an unsound non-theorem requires an agent to overclaim
affirmatively.

**The judge** combines the rollout's observation with the agent's word:

```
state verifiably closed              -> PROVED     -> Theorem / Unsatisfiable
AGENT_DONE and claims_exhausted      -> EXHAUSTED  -> CounterSatisfiable / Satisfiable
AGENT_DONE otherwise                 -> GAVE_UP    -> GaveUp
STEP_BUDGET / TIME_BUDGET            -> RESOURCE_OUT
```

Closure is verified first, from the state itself, whatever the agent said: a
proof found on the last budgeted step is still a proof, and an agent that
believed it closed when the state disagrees is an error, never a proof.

**The warrant.** An exhaustion claim is licensed only by systematic coverage
of a complete fragment of the action space. Discipline may ignore rule
families redundant for completeness -- factorization -- and keeps the claim; it
forfeits the claim when it prunes ones that are not: cut, scut, conjecture
start, or a depth bound that ever bound. leanCoP's `comp(N)` restores the
claim by switching the final iterations to complete mode.

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
constraints.

**pycop** can pool trivially: its attempt is `run(problem, schedule)`, and both
arguments are picklable. In practice a subprocess per problem is simpler still,
because `subprocess.run(timeout=)` kills and reaps a child that will not stop,
which no worker pool does, and OOM arrives as a signal in the return code. The
command it spawns is its own CLI -- the one CASC invokes -- so there is one path
rather than two.

The result is threads around processes: a thread waiting on a subprocess is
blocked in `waitpid` and holds no lock, so a thread per core is enough to keep
the cores busy.

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

## The model-based agent

An agent is one function, `__call__(state) -> Action | None`, plus `status()`
for its word about its own search. Most of the family here is R&N's
model-based agent, implemented as a memory and a chooser:

```python
class Memory(Protocol):
    def exposed(self, agent, state) -> Sequence[Action]   # A(s, μ) ⊆ A(s)
    def update(self, agent, state, action) -> None        # U_π
    # both receive the agent: config from agent.options, status onto agent

OnlineSearchAgent(memory, choose)
```

| memory -- what `A(s, μ)` exposes | chooser -- among what it exposed |
|---|---|
| none (markov) | `first` |
| `DFSMemory`: the choicepoint stack | learned scorer |
| `IDMemory`: stack plus depth ladder | |

leanCoP is `OnlineSearchAgent(IDMemory(), first, options)` -- the
`traced_leancop_agent` factory in pycop. A learned agent keeps the memory and replaces
the chooser, which is where the old multiple-inheritance diamond dissolved
into composition. The warrant lives in the memory's `status()`: only the
memory knows whether its options pruned, so only it can claim
`DFS_EXHAUSTED` or `ID_FIXED_POINT`, and it answers `GAVE_UP` otherwise.

This factoring is a convenience for reactive agents, not a law. A planner --
an rlCoP-style Monte-Carlo search -- runs thousands of transitions between
being handed a state and returning an action, needing the transition function
and state copies to do it. That fits neither slot, so a planner implements
`Agent` directly and keeps its tree in its own state.

## Memory strata and episodes

An episode boundary is an exogenous transition: a state change not caused by
the agent's action. Corpus, problem, strategy and budget are four sources of
the same event, differing in what changes -- and agent memory has strata with
matching validity scopes, managed by the agent, keyed off what it observes:

| stratum | valid across | invalidated by |
|---|---|---|
| derivation-bound (frontier, stack) | one attempt | reset to ε, even same ω |
| ω-bound (statistics, shadow structures) | attempts within ω | new ω |
| persistent (θ) | everything | nothing |

Two consequences. Carried memory that *orders* preserves the exhaustion
warrant; carried memory that *prunes* forfeits it, per episode. And
exchangeability is a protocol property, purchased by resetting: zero-shot
evaluation constructs fresh agents per problem, intra-conjecture experiments
deliberately do not, and the report says which. With θ frozen, episodes are
exchangeable and parallelism is free at any boundary; with θ advancing, every
trajectory is stamped with what generated it, and rounds -- θ
piecewise-constant, updates at the barrier -- buy back full parallelism, which
is why proof aggregation parallelises so painlessly.
