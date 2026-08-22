# Constraints

What makes a connection admissible. `constraints` sits directly on `syntax` and
answers one question for the calculus: may these two literals be connected, and
at what cost to the substitution.

## One transaction, several algorithms

A rule application is admissible only if term arguments unify, prefixes satisfy
the accessibility conditions of the logic and domain, and the clause-local free
variables remain admissible. Three different checks, but one decision, so they
share one boundary:

```python
delta = state.constraints.delta_for_literals(
    older=path_literal,
    older_instance=path_instance,
    newer=goal_literal,
    newer_instance=goal_instance,
    logic=state.matrix.logic,
    domain=state.matrix.domain,
)
```

`ConstraintDelta | None` rather than `(bool, updates)`: `None` means not
admissible, an empty delta means admissible with nothing to commit. With several
families of update, the option type says the same thing with one fewer way to
misuse it.

```python
@dataclass(frozen=True, slots=True)
class ConstraintDelta:
    term_bindings: tuple[TermBinding, ...] = ()
    prefix_equations: tuple[PrefixEquation, ...] = ()
    free_variables: tuple[FreeVariableReference, ...] = ()
```

## Query, commit, roll back

Candidate generation is side-effect free. `Dynamics` asks for a delta per
candidate and throws away the ones the policy does not choose; only the selected
action commits.

| | |
|---|---|
| `satisfied_literals` | the current eager constraints already make these literals identical -- Prolog's `==`, so term bindings are visible but lazy prefix equations are not solved |
| `delta_for_literals` | connecting these literals is consistent with the store; here is what to add |
| `delta_for_free_variables` | these clause-local references are consistent with the store |
| `commit` | add a selected delta, tagged with the rule application that owns it |
| `rollback_owned_by` | remove the constraints owned by undone rule applications |

Ownership is what makes undo definable. Every committed binding is tagged with
the `RuleApplicationId` that introduced it, so pruning at a node knows exactly
which constraints to retract.

!!! warning "Ownership is not dependence"

    A delta records what an application *introduced*, not what it *consumed*. An
    application that succeeded because of an earlier binding, without adding one
    of its own, has no recorded link to that binding -- so retracting it leaves
    no trace here. This is the mechanism behind the non-chronological undo gap
    described in [dynamics](dynamics.md).

## Term and prefix are not one algorithm

Term unification asks whether atom arguments can be made equal under first-order
substitution. Prefix unification asks whether prefixes satisfy the accessibility
conditions for a given logic and domain, and the leanCoP-family reference code
uses genuinely different predicates for the intuitionistic, modal, cumulative
and varying-domain cases.

They are also solved differently. Term constraints are eager: a binding is
applied when committed. Prefix constraints are lazy: equations accumulate and
are checked for satisfiability against the current set, which is closer to the
`PreSet` style of the reference provers and avoids committing to a prefix
assignment that a later connection would have to undo.

Collapsing them into one recursive function would hide a real distinction to buy
a small amount of shared code. What the two share is the transaction, not the
algorithm.

## Free variables

Clause-local `free_variables` correspond to the `FV`/`FreeV` lists in the
reference Prolog. The constraint layer reads them as modal domain conditions for
the modal case and as the additional quantifier/prefix condition for the
intuitionistic case. `Start` and `Extension` add the selected clause's free
variables as instance-scoped references, and a candidate is checked against both
active and pending references before it is accepted.

One subtlety survives from the intuitionistic translator and is easy to get
wrong: source negation and internal negative polarity are not the same
operation. A positive source `~ A` adds a Skolem prefix part and then translates
`A` at negative polarity, so `all X: ~ p(X)` extends the prefix twice -- once for
the quantifier, once for the negation. The reference translator skips the
quantifier extension only for an internal negative body produced by polarity
rewriting, never for source negation syntax.

## Layout

    term.py               TermSubstitution, TermBinding, tableau-variable scoping
    term_unification.py   the eager unifier
    prefix.py             PrefixConstraintStore, PrefixEquation, PrefixBinding
    prefix_unifier.py     direct prefix unification per logic and domain
    delta.py              ConstraintDelta
    store.py              ConstraintStore, the one boundary the calculus sees

Native prefix unification currently covers modal `D`, `T`, `S4` and `S5` direct
prefix unification, plus the intuitionistic prefix rule, each checked against
the corresponding reference predicate.

## Where regularity lives

Regularity is a constraint check but not a constraint object: it asks whether a
transition would place two equal same-polarity literals on one branch under the
substitution that transition produces. It is an admissibility side condition, so
it belongs to the calculus rather than to a policy -- an irregular edit is not
something a policy declines to choose, it is something `T` does not admit.
