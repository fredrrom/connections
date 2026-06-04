# Prover API

This document records the public prover boundary for `connections` 0.1. The
goal is a small API that can be used by symbolic provers, custom policies, and
corpus runners without subclassing the prover loop.

## Ownership

`connections` owns the transition system and the concrete loop that operates a
policy against that transition system. Callers provide a problem path, problem
options, strategies, and hooks. Strategies create fresh policies for each
scheduled attempt.

Extensions should not override `Prover.run`. They should provide a strategy or
a hook:

- a strategy changes matrix construction, symbolic policy options, and policy
  construction
- a hook observes choices, transitions, proof discovery, and strategy
  completion without replacing the transition function

## Main Types

`Prover`
: Concrete runner over a problem path and one or more scheduled strategies. It
  builds a fresh `State` per strategy, asks the strategy for a fresh policy,
  calls `policy(state)` until the tableau closes or the policy reports a
  terminal outcome, and maps the internal outcome to SZS status. The `run`
  method is generic over the supplied strategy type; the `Prover` object itself
  carries no strategy state. Logic, domain, and include roots are direct
  `run(...)` arguments.

`Problem`
: Runtime problem object containing the `Matrix`, start-clause mode, logic, and
  domain. It computes the actual start-clause ids from matrix indices.

`MatrixOptions`
: Matrix construction settings shared by strategies:
  `translation`, `reorder`, and `start_clauses`.

Strategy object
: Attempt recipe. A strategy has `matrix: MatrixOptions` and
  `create_policy() -> Policy`. This is a structural contract rather than a
  public base class. The strategy is immutable configuration; the returned
  policy is fresh mutable search state for one scheduled attempt.

`DFSStrategy`
: Generic DFS strategy composition. It carries `MatrixOptions` plus
  `DFSOptions`, and creates a fresh `DFSPolicy` for each attempt.

`StrategySchedule`
: Immutable sequence of `ScheduledStrategy` entries. Each entry carries a
  strategy plus optional step and timeout budgets. `from_weighted` divides a
  shared budget according to weights.

`Policy`
: Stateful action-selection object. The required contract is:

```python
actions = policy.available_actions(state)
action = policy.next_action(state, actions)
```

The public `policy(state)` call wraps this contract, validates that the selected
action belongs to the available action set, records the choice, and returns an
`ActionChoice`.

`ActionChoice`
: The selected action plus its index in the policy's current action tuple. Hooks
  can use this without re-querying policy internals.

`ApplyAction`, `UndoAction`, and `ApplyActions`
: Public action records from `connections.prover.actions`. `Dynamics` creates
  these records, policies choose among them, and `Prover` executes the selected
  record. The action records are separate from `Dynamics` so callers can type
  action spaces without importing transition-system internals.

`ProverHook`
: Lifecycle observer with these methods:

- `on_strategy_start(strategy_index, entry)`
- `on_choice(state, choice)`
- `on_transition(state, action)`
- `on_proof_found(state)`
- `on_strategy_end(result, state)`

Hooks must treat `state` as live mutable prover state. They may inspect it, but
they should not mutate the tableau or constraints.

`ProverOutcome`
: Internal stop reason. `PROVED` means the tableau closed. `DFS_EXHAUSTED` and
  `ID_FIXED_POINT` mean search ended without a closed tableau. `TIMEOUT`,
  `STEP_BUDGET`, and `ERROR` are no-success outcomes above the tableau level.

`SZSStatus`
: Reported TPTP status derived from `ProverOutcome` and whether the source
  problem had a conjecture.

## Running A Problem

```python
from connections.prover import Prover
from connections.pycop.strategy import PycopStrategy

result = Prover().run(
    "problem.p",
    strategy=PycopStrategy(),
    logic="classical",
    domain="constant",
)

print(result.outcome)
print(result.szs_status)
```

For budgeted or scheduled runs:

```python
from connections.prover import Prover, StrategySchedule, WeightedStrategy
from connections.pycop.strategy import PycopStrategy

schedule = StrategySchedule.from_weighted(
    [
        WeightedStrategy(PycopStrategy(), weight=1),
    ],
    steps=1000,
    timeout_seconds=5.0,
)

result = Prover().run("problem.p", schedule=schedule)
```

## Policies

Policies are the extension point for action choice. A policy should not apply
actions directly. It should only return one of the actions it exposes.

```python
from connections.policy import Policy

class FirstActionPolicy(Policy):
    def available_actions(self, state):
        ...

    def next_action(self, state, actions):
        return actions[0]
```

The built-in symbolic policies are:

- `DFSPolicy`: depth-first traversal over a `Frame(goal_id, actions)` stack,
  synchronized to the first open fringe goal
- `IterativeDeepeningPolicy`: DFS plus path-limit iteration
- `PycopPolicy`: leanCoP-compatible policy configuration

`cut` and `scut` are DFS options. `comp(I)` is an iterative-deepening option.

Policy action spaces are legal-action spaces. In particular,
`Dynamics.apply_actions(state, goal)` returns only actions whose term,
prefix/domain, and free-variable constraints currently succeed.
`IterativeDeepeningPolicy` applies the path limit to that legal-action list.
It does not expose or count candidates that the constraint store rejects.

## Hooks

Hooks observe the prover loop after policy choice and after transition.

```python
from connections.prover import ProverHook

class CountingHook(ProverHook):
    def __init__(self):
        self.choices = 0

    def on_choice(self, state, choice):
        self.choices += 1
```

`on_proof_found(state)` is called when a strategy closes the tableau. Hooks can
use it to inspect the final state before `on_strategy_end`.

## Matrix Construction

`Prover` constructs matrices through `connections.clausification.matrix_from_file`
using the active strategy's `MatrixOptions` and the active problem path/options.
`Matrix` itself is a core data structure and does not own parsing or
clausification. Matrix objects are cached per run by:

- source file path
- logic and domain
- source include directories
- translation mode
- reorder value
- start-clause mode

The 0.1 native matrix path supports:

- classical `fof(...)`
- classical `cnf(...)`
- initial prefix-annotated intuitionistic `fof(...)`
- initial prefix-annotated modal `qmf(...)`

Mixed CNF/non-CNF source files are explicit errors.

## Source Directories

`connections` does not implicitly read benchmark locations from `TPTP`, `ILTP`,
or `QMLTP` environment variables. Pass include roots explicitly through
`Prover.run(..., source_file_dirs=...)` in APIs or `--source-dir` in tools.

## Stability Boundary

Stable for 0.1:

- `connections.prover.Prover`
- `connections.prover.ProverHook`
- `connections.prover.Problem`
- `connections.prover.StrategySchedule`
- `connections.prover.MatrixOptions`
- `connections.prover.DFSStrategy`
- `connections.prover.ApplyAction`
- `connections.prover.ApplyActions`
- `connections.prover.UndoAction`
- `connections.policy.Policy`
- `connections.policy.DFSPolicy`
- `connections.policy.IterativeDeepeningPolicy`
- `connections.policy.DFSOptions`
- `connections.policy.IterativeDeepeningOptions`
- `connections.pycop.PycopStrategy`
- `connections.core.status`

Internal for 0.1:

- tableau storage details
- rule cache internals
- exact action ordering beyond the policy's exposed tuple
- Prolog reference assets under `tools/parity/reference_provers`
