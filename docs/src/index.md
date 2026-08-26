# Connections

A library of primitives for clausal connection tableaux, and the provers and
learning code built on it.

Connection-tableau construction is a transition system. A matrix *M* induces

    P(M) = (S, A, s0, T, S✓)

whose states are annotated partial tableaux, whose actions are tableau edits,
and whose accepting states are the closed tableaux. A proof procedure is a
policy acting in that system. leanCoP's depth-first search, restricted
backtracking, Monte-Carlo planning and a learned scorer differ only in what the
policy remembers and how it chooses -- not in the system they act in.

That is the whole design. `connections` provides the system; everything else
here provides policies.

## Start here

| | |
|---|---|
| [Install](guides/install.md) | the workspace, or just the library |
| [Prove a problem](guides/prove-a-problem.md) | the CLI and the Python entry points |
| [Write an agent](guides/write-an-agent.md) | one function, and what it may assume |

## The design notes

The notes are where boundaries are settled and argued. They describe the target,
which the code does not yet match everywhere.

| | |
|---|---|
| [Architecture](design/architecture.md) | the map: what is in the library, what is a package |
| [Language](design/language.md) | source file to matrix |
| [Constraints](design/constraints.md) | what makes a connection admissible |
| [Dynamics](design/dynamics.md) | states, actions, transitions, undo |
| [Running](design/running.md) | rollout, strategy, schedule, run, limits, SZS |

## Packages

| | |
|---|---|
| [pycop](packages/pycop.md) | leanCoP-equivalent prover, parity harness, CLI |
| [imitation](packages/imitation.md) | learning agent: critic, graph model, trainer, measures |

## Scope

Classical, intuitionistic and modal connection tableaux. Native TPTP parsing and
matrix construction, with no implicit reading of corpus environment variables.
Symbolic policies checked for parity against the leanCoP family.

`connections` handles one problem at a time and ships no runner: nothing in it
starts a process, manages a pool, or writes a file. That is where CASC draws the
line too, and it leaves how to spend a machine to whoever owns the machine.
