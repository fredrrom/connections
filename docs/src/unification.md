# Unification And Constraints

This note records the intended boundary for term unification, prefix
unification, and free-variable admissibility in `connections`.

## Current State

The prover state owns one mutable constraint object:
`connections.constraints.ConstraintStore`.

It is used by `Dynamics` to test rule candidates:

- extension
- reduction
- factorization
- regularity

Candidate generation is side-effect free. A unification query returns
`ConstraintDelta | None`, and `State.apply_rule` commits that delta only when
the policy chooses the action. `State.undo_rule_application` removes
constraint updates owned by the reverted rule application.

Native prefix unification has started as a narrow parity slice in
`connections.constraints.prefix`. It currently supports modal `D`, `T`, `S4`,
and `S5` direct prefix unification against the mleanCoP oracle, plus the
iLeanCoP intuitionistic prefix rule. The direct unifier returns
`PrefixBinding`s as witness data for parity checks. During proof search,
prefix constraints are committed as equations rather than eager bindings,
matching the leanCoP-family `PreSet` style more closely. Clause-local
`free_variables` match the `FV`/`FreeV` lists in the Prolog code. The
constraint layer interprets them as modal domain conditions for mleanCoP and
as iLeanCoP's additional quantifier/prefix condition.

## Boundary

The prover should have one constraint boundary, even if the algorithms inside
it remain separate.

```python
delta = state.constraints.delta_for_literals(
    older=path_literal,
    older_instance=path_instance,
    newer=goal_literal,
    newer_instance=goal_instance,
    logic=state.problem.logic,
    domain=state.problem.domain,
)
if delta is not None:
    action = ApplyAction(goal_id, Reduction(source_goal_id, delta))
```

The important property is not that term and prefix unification share one
algorithm. The important property is that a rule application gets one
transactional update batch:

- term bindings
- prefix equations
- free-variable admissibility checks

That batch is committed by the selected action and undone by rule-application
owner.

## Data Shape

The current store keeps eager `TermSubstitution` and lazy
`PrefixConstraintStore` components behind one transaction boundary.

The implementation lives under `connections/constraints/`:

- `term.py`: `TermSubstitution`, `TermBinding`, tableau-variable scoping
- `prefix.py`: `PrefixConstraintStore`, `PrefixEquation`,
  `PrefixBinding`, direct prefix and free-variable admissibility
  parity rules
- `delta.py`: `ConstraintDelta`
- `store.py`: `ConstraintStore`

```python
TermBinding = tuple[TermSubstitutionVariable, TermReference]


@dataclass(frozen=True, slots=True)
class PrefixBinding:
    variable: PrefixVariable
    target: PrefixReference


@dataclass(frozen=True, slots=True)
class PrefixEquation:
    left: Prefix
    right: Prefix


@dataclass(frozen=True, slots=True)
class ConstraintDelta:
    term_bindings: tuple[TermBinding, ...] = ()
    prefix_equations: tuple[PrefixEquation, ...] = ()
    free_variables: tuple[FreeVariableReference, ...] = ()


class ConstraintStore:
    def satisfied_literals(..., logic: str, domain: str) -> bool: ...
    def delta_for_literals(..., logic: str, domain: str) -> ConstraintDelta | None: ...
    def delta_for_prefixes(..., logic: str, domain: str) -> ConstraintDelta | None: ...
    def delta_for_free_variables(..., logic: str, domain: str) -> ConstraintDelta | None: ...
    def commit(delta: ConstraintDelta, *, owner_app_id: int | None = None) -> None: ...
    def rollback_owned_by(owner_app_ids: tuple[int, ...] | set[int]) -> None: ...
```

`ConstraintDelta | None` is cleaner than `(bool, updates)` once there are
multiple update families. `None` means the candidate is not admissible. An
empty delta means no new constraint has to be committed.

The terminology is:

- `satisfied_literals`: the current eager constraints already make the literals
  identical. This mirrors Prolog `==`: term substitutions are visible, but lazy
  prefix equations are not solved or applied.
- `delta_for_literals`: adding this literal relation is consistent with the
  current store; return the term bindings and prefix equations to add.
- `delta_for_free_variables`: adding these clause-local free-variable
  references is consistent with the current store.
- `commit`: mutate the store by adding a selected delta.
- `rollback_owned_by`: remove committed constraints owned by backtracked rule
  applications.

The first migration steps are in code: rule dataclasses carry
`ConstraintDelta`, the classical path stores existing term bindings in
`ConstraintDelta.term_bindings`, non-classical literal unification adds scoped
equations in `ConstraintDelta.prefix_equations`, and `Start`/`Extension`
rules add selected clause `free_variables` as instance-scoped
`ConstraintDelta.free_variables`. `ConstraintStore.delta_for_literals` checks
active and candidate free-variable references against the pending term
bindings before accepting a candidate. `State` commits through
`ConstraintStore`, so selected rule applications remain one transactional
update batch.

## Term Versus Prefix Semantics

Term unification and prefix unification should not be collapsed into one
recursive function too early.

Term unification answers whether atom arguments can be made equal under
first-order substitution.

Prefix unification answers whether prefixes satisfy the accessibility
conditions for the selected logic and domain. The leanCoP-family Prolog code
uses different prefix predicates for intuitionistic, modal, cumulative, and
varying-domain cases. That logic should remain explicit.

One subtle point in the intuitionistic translator is that source negation and
internal negative polarity are not the same operation. A positive source
`~ A` adds a Skolem prefix part and then translates `A` under negative
polarity. A positive source `all X: ~ p(X)` therefore extends the prefix once
for the universal quantifier and once for the source negation. The Prolog
translator only skips the universal-quantifier prefix extension for an
internal negative body introduced by polarity rewriting, not for source
negation syntax.

The shared abstraction should therefore be the transaction interface, not a
single universal unification algorithm. Term constraints are solved eagerly;
prefix constraints are accumulated as equations and checked for satisfiability
against the current equation set.

## Dynamics Integration

`Dynamics` should call `state.constraints` for candidate deltas and current
satisfaction.

Old shape:

```python
unifies, updates = state.substitution.unify_literals(...)
if unifies:
    return Reduction(source_id, updates)
```

Current shape:

```python
delta = state.constraints.delta_for_literals(
    ...,
    logic=state.problem.logic,
    domain=state.problem.domain,
)
if delta is not None:
    return Reduction(source_id, delta)
```

The `Rule` dataclasses should then carry `ConstraintDelta` rather than raw
term bindings. This keeps extension, reduction, and factorization uniform, and
keeps undo logic local to the state/constraint-store boundary. Classical
ground-literal shortcuts still preserve the old behavior; non-classical
candidates go through the store so prefix deltas are not skipped.

## Diagnostics

The direct prefix, prefix-equation, and free-variable admissibility parity tools
exercise the constraint layer before full prover runs. They compare native
constraint checks with the bundled leanCoP-family reference predicates and are
kept under `tools/parity/` as explicit developer diagnostics.

Full prover parity is checked separately with matrix, status, and trace tools.
Those broader checks verify parser plus matrix construction, SZS outcomes, and
policy-visible search-event order.
