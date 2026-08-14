# satresetcop

A connection prover that couples first-order search without equality to an
incremental SAT solver, and restarts the tableau rather than backtracking
locally when new ground clauses appear.

!!! note "Not yet in this workspace"

    `satresetcop` is a separate codebase being merged in. This page records the
    design so the boundary is settled before the move; nothing under
    `packages/satresetcop/` exists yet.

## The idea

Two ways to finish, over the same *P(M)*.

**Close a tableau**, as any connection prover does.

**Or refute propositionally.** Every clause copy the tableau makes is grounded
and added to a shadow CNF, which an incremental SAT solver is run over. If that
accumulated set of ground instances is unsatisfiable, the matrix is
unsatisfiable by Herbrand's theorem, and the search stops with no closed tableau
at all. This is instance-based reasoning in the style of Inst-Gen, reached from
a connection calculus.

**Reset** is what makes the second route pay. On reaching a dead end with new
ground clauses available, the tableau, substitution and proof sequence are
discarded, but the shadow CNF is kept. Local backtracking is traded for diverse
clause generation while the SAT state accumulates across restarts.

## Where it fits

Reset is a policy decision -- when to give up on this tableau -- so it belongs
in the policy, and the shadow CNF is policy memory *μ* in the sense of
[running](../design/running.md#composing-policies). The grounding of clause
copies is the one part that touches the calculus, since it needs to see each
rule application as it happens.

That keeps `T` untouched: satresetcop is a different policy over the same
transition system, not a different calculus. Its extra terminal condition is a
result the policy reports, not a transition the system admits.

## Proof output

The propositional route means the proof object is not a tableau. What the
system holds when it stops is a set of ground instances and the solver's word
that they are jointly unsatisfiable, so the derivation it emits is:

    input formulas          -> clausify        -> the matrix
    matrix                  -> split_conjunct  -> individual clauses
    clauses                 -> instantiate     -> ground instances
    ground instances        -> sat_refutation  -> $false

!!! warning "Clausify provenance"

    In the CASC-J13 entry, `clausify` consumes every input formula in one step,
    so the largest inference in a proof has as many parents as the problem has
    formulas -- 455 on average, 8006 at worst across that run. This comes from
    clausifying through a translation that carries no per-formula provenance, so
    a checker cannot attribute any clause to any axiom and leaf verification is
    incomplete.

    The fix is one `clausify` step per input formula, which needs provenance
    threaded through clausification rather than a change to the printer.

TSTP output is a capability `connections` does not currently have -- `run`
returns a `Result` that serialises to JSON. A TSTP printer belongs on the `run`
side, since it reports a result rather than constructing one, and it is shared
with any other package that wants to enter a competition.

## Reading

The CASC-J13 system description and sample solution are at
[tptp.org/CASC/J13](https://tptp.org/CASC/J13/SystemDescriptions.html).
