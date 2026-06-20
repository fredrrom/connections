# Prover API

This document records the public prover boundary for `connections` 0.1. The
goal is a small API that can be used by symbolic provers, custom policies, and
corpus runners without subclassing the prover loop.

## Ownership

`connections` owns the transition system and the concrete loop that operates a
policy against that transition system. Callers provide a problem path, problem
semantics, and a strategy schedule. Strategies create the search space
and fresh policies for each scheduled attempt.

Extensions should not override `Prover.run`. They should provide strategies
that change search-space construction, symbolic policy options, and policy
construction.

## Main Types

`Prover`
: Concrete runner over a `ProblemSpec` and one scheduled strategy sequence. It
  builds a fresh `State` per strategy, asks the strategy for a fresh policy,
  calls `policy(state)` until the tableau closes or the policy reports a
  terminal outcome, and maps the internal outcome to SZS status. The `run`
  method is generic over the supplied strategy type; the `Prover` object itself
  carries no strategy state.

`ProblemSpec`
: Problem input and semantics: source path, logic, domain, and include roots.
  Logic affects matrix translation and proof-search constraints. Domain is part
  of the proof-search semantics and is used by prefix/domain constraints; the
  current matrix parser accepts it but does not change parsing based on domain.

`Problem`
: Runtime problem object containing the `Matrix`, start-clause mode, logic, and
  domain. It computes the actual start-clause ids from matrix indices.

`MatrixOptions`
: Search-space construction settings shared by strategies:
  `translation`, `reorder`, and `start_clauses`.

Strategy object
: Attempt recipe. A strategy is a plain mapping with `matrix` options and
  `policy` options. `Prover.run` receives a policy factory from the concrete
  prover or experiment layer. That factory interprets the strategy and creates
  fresh mutable policy state for one scheduled attempt.

`StrategySchedule`
: Immutable sequence of `ScheduledStrategy` entries. Each entry carries a
  strategy plus optional step and timeout budgets. This is the public execution
  unit for `Prover.run`. `from_weighted` divides a shared budget according to
  weights.

`Policy`
: Stateful action-selection object. The prover calls `policy(state)` and
  receives an `Action` or `None`. Search policies such as DFS and ID refine
  this with `ProverOutcome` for exhausted search. Learning libraries that need
  state/action records should wrap a policy outside `connections`; the base
  prover API does not carry serialized observations or labels.

`ApplyAction`, `UndoAction`, and `ApplyActions`
: Public action records from `connections.prover.actions`. `Dynamics` creates
  these records, policies choose among them, and `Prover` executes the selected
  record. The action records are separate from `Dynamics` so callers can type
  action spaces without importing transition-system internals.

`ProverOutcome`
: Internal stop reason. `PROVED` means the tableau closed. `DFS_EXHAUSTED` and
  `ID_FIXED_POINT` mean search ended without a closed tableau. `TIMEOUT`,
  `STEP_BUDGET`, and `ERROR` are no-success outcomes above the tableau level.

`SZSStatus`
: Reported TPTP status derived from `ProverOutcome` and whether the source
  problem had a conjecture.

## Running A Problem

```python
from connections.prover import ProblemSpec, Prover, StrategySchedule

from provers.pycop import LeancopSettingsCodec

problem = ProblemSpec("problem.p", logic="classical", domain="constant")
schedule = StrategySchedule.single(LeancopSettingsCodec.from_tokens(["cut", "comp(7)"]))

result = Prover().run(
    problem,
    schedule=schedule,
)

print(result.outcome)
print(result.szs_status)
```

For budgeted or scheduled runs:

```python
from connections.prover import (
    ProblemSpec,
    Prover,
    StrategySchedule,
    WeightedStrategy,
)
from provers.pycop import LeancopSettingsCodec

problem = ProblemSpec("problem.p")
schedule = StrategySchedule.from_weighted(
    [
        WeightedStrategy(LeancopSettingsCodec.from_tokens(["cut"]), weight=1),
    ],
    steps=1000,
    timeout_seconds=5.0,
)

result = Prover().run(
    problem,
    schedule=schedule,
)
```

## Policies

Policies are the extension point for action choice. A policy should not apply
actions directly. Its only public operation is `__call__(state)`.

```python
from connections.policy import Policy

class MyPolicy(Policy):
    def __call__(self, state):
        ...
```

DFS and ID are stateful search policies. Their public operation is still
`__call__(state)`, but subclasses normally override the protected
`_next_action(state, actions)` hook to rank actions after the search policy has
restricted the action space. DFS and ID may return `ProverOutcome` when search
is exhausted.

The built-in symbolic policies are:

- `DFSPolicy`: abstract depth-first search shell over work and choicepoint
  frames
- `IDPolicy`: abstract DFS plus path-limit iteration

Concrete provers or experiments subclass these policies to implement action
choice. `provers.pycop.PycopPolicy` is `IDPolicy` with first available action
choice. `cut` and `scut` are DFS options. `comp(I)` is an iterative-deepening
option.

Policy action spaces are legal-action spaces. In particular,
`Dynamics.apply_actions(state, goal)` returns only actions whose term,
prefix/domain, and free-variable constraints currently succeed.
`IDPolicy` applies the path limit to that legal-action list.
It does not expose or count candidates that the constraint store rejects.

## Closed Proof State

When a strategy closes the tableau, `StrategyResult.closed_state` stores the
closed state for that strategy. If the whole schedule proves the problem,
`ProverResult.closed_state` points at the winning closed state. Callers that
need proof-path extraction should consume that result state after `run`
returns.

## Matrix Construction

`Prover` constructs matrices through `connections.clausification.matrix_from_file`
using the active strategy's `MatrixOptions` and the active `ProblemSpec`.
`Matrix` itself is a syntax-level data structure and does not own parsing or
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
`ProblemSpec(..., source_file_dirs=...)` in APIs or `--source-dir` in tools.

## Stability Boundary

Stable for 0.1:

- `connections.prover.Prover`
- `connections.prover.Problem`
- `connections.prover.ProblemSpec`
- `connections.prover.StrategySchedule`
- `connections.prover.Strategy`
- `connections.prover.MatrixOptions`
- `connections.prover.PolicyOptions`
- `connections.prover.ApplyAction`
- `connections.prover.ApplyActions`
- `connections.prover.UndoAction`
- `connections.policy.Policy`
- `connections.policy.DFSPolicy`
- `connections.policy.IDPolicy`
- `connections.policy.IterativeDeepeningOptions`
- `provers.pycop.LeancopSettingsCodec`
- `connections.prover.status`

Internal for 0.1:

- tableau storage details
- rule cache internals
- exact action ordering beyond the policy's exposed tuple
- Prolog reference assets under `tools/parity/reference_provers`
