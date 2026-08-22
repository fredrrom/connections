# Dynamics

The transition system a policy acts in. This is `calculus/`, sitting on
`syntax` and `constraints` and knowing nothing above it: no budgets, no
schedules, no statuses, no processes, and no problems-as-files.

## The system

A matrix *M* induces a transition system

    P(M) = (S, A, s0, T, S✓)

whose states are annotated partial connection tableaux for *M*, whose actions
are tableau edits, whose initial state is the empty tableau, and whose goal set
*S✓* is the closed tableaux. `T` is partial: it is defined exactly on the edits
the calculus admits at a state, and `A(s)` denotes the actions enabled there.

Notation is the inter-conjecture paper's, unchanged. Where this doc and the
thesis describe the same object they use the same symbols for it.

Everything a proof needs is in the state. Nothing about *how* the tableau was
built is -- no stack, no depth bound, no record of what has been tried. That
belongs to a policy.

## What a state holds

The state is *[d, ω]*: the derivation together with its static context. The
derivation is the tableau, the rigid substitution accumulated so far, and the
proof-object annotations undoing needs. The context ω is the matrix itself,
stamped with its logic and domain -- they parameterize which connections are
admissible and whether a closed tableau's constraints are satisfiable, so two
stamps over the same clauses are two transition systems. Identity is by
content: the same matrix reached through different formulations compares
equal, which is what lets agent memory about ω transfer on content rather than
provenance. Turning a *file* into a state is parsing and clausification,
which is `run`'s job, not the calculus's.

The static/dynamic split is load-bearing beyond tidiness: relabelling a
trajectory rewrites the context half of *[d, ω]*, and that is only legal
because ω never contaminates *d*.

## Actions

An edit either extends the tableau or removes part of it.

**Applying a rule** to an open goal: start, extension, reduction, or
factorization. Each records what it introduced -- the nodes it added and the
constraints it posted -- so that undoing it is well defined.

Start selection and factorization scope are the agent's query options, not
system configuration: the calculus validates whatever it is asked about, and
which clauses may start or which factorization family to consider is the agent
asking for a subset, exactly analogous on both counts. What keeps this sound
is the completeness criterion in [running](running.md): ignoring redundant
rule families is free, pruning non-redundant ones forfeits the exhaustion
claim.

**Undoing an application** at a node. Any application the tableau carries may be
undone, not only the most recent, so the action space is not a stack. A policy
that wants stack discipline imposes it in its own memory; the system does not.

## What a transition guarantees

Soundness rests here. A policy that acts only through `T` produces a sequence of
valid partial tableaux, so any accepting state it reaches is a checkable closed
tableau. Nothing a policy does can produce an unsound proof, because `T` admits
only edits the calculus permits.

Completeness rests elsewhere. Whether the reachable accepting states are ever
reached depends on how a policy explores, and a policy that prunes -- as
restricted backtracking does -- may make some unreachable. That distinction
matters for what an exhausted search is allowed to claim; see
[running](running.md).

## Undoing

A prune removes the dependent rule applications and resets the constraints they
introduced. Because the substitution is global, dependence is not confined to
the pruned subtree: an application elsewhere may have been justified by a
binding the prune retracts.

Three properties make arbitrary-node undo well defined:

- **The solved form depends on the set of live applications, not their order.**
  A most general unifier is a function of the constraint set, so removing a
  constraint and re-solving gives the same result however the survivors were
  ordered.
- **Acyclicity is preserved.** A surviving binding set is a subset of one that
  already passed an occurs check.
- **Regularity cannot be newly violated.** Pruning only weakens the
  substitution, and regularity forbids equal literals on a branch.

What remains is the obligation to re-validate closures whose justification was
retracted, and to cascade when reopening one invalidates another.

!!! warning "Known gap"

    The implementation does not do this. Constraint deltas record only what an
    application introduced, keyed by a flat owner, so an application that
    consumed an earlier binding without introducing one of its own has no
    recorded dependence on it. Closedness is a cached boolean recomputed from
    tree structure alone. A non-chronological undo can therefore leave a goal
    marked closed whose connection no longer holds. Shipped depth-first policies
    do not trigger it, because their undos happen to be chronological; a policy
    with the full action space can.

## Regularity

A regularity condition removes a transition from consideration when it would put
two equal same-polarity literals on one branch, under the substitution that
transition produces. It is an admissibility side condition, so it lives in the
system rather than in a policy: an irregular edit is not something a policy may
choose to avoid, it is something `T` does not admit.

## The boundary with policies

`Dynamics` decides what is admissible. A policy decides what to do among the
admissible. The interface between them is one function:

```python
Policy = Callable[[State], Action | None]
```

Everything a policy wants to remember -- a stack of untried alternatives, a
depth bound, a search tree, a learned scorer -- is its own state, and none of it
is visible to the system. That is what makes a leanCoP-style search and a
planner instances of the same interface rather than variants of the system.

The composition of policies from smaller parts, and why it fits reactive
policies but not planners, is in [running](running.md).

!!! warning "Known gap: ID overclaims a fixed point"

    Two m2k problems (t100_relat_1, t10_enumset1) draw CounterSatisfiable under
    cut+comp(7) where leanCoP proves Theorem. The flag lifecycle through the
    comp switch is correct; the failure is that at the final depth the agent
    detects zero gate-blocked unifiable candidates while the reference still
    finds them and deepens. The divergence is in which candidates reach the
    depth gate at the limit boundary. Pinned as strict xfail in
    tests/unit/run/test_known_overclaims.py; the scut/cut variants are already
    honest GaveUp through the warrant gate.

!!! warning "Known gap"

    Iterative deepening does not respect this boundary today. Trace-parity work
    against `{i,m}leanCoP` pushed path-limit tracing and extension-candidate
    bookkeeping into the policy, so legal action generation is no longer
    entirely `Dynamics`'. The current behaviour is what parity requires and
    should not be changed to fix the layering; the target is an ID that is again
    a small search-control layer over DFS, with candidate generation back where
    it belongs.
