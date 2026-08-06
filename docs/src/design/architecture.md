# Architecture

This repository is a uv workspace. `connections` is the library; the packages
under `packages/` are built on it. This note is the map. The transition system
is described in [dynamics](dynamics.md), and everything from a rollout up to
running a corpus in [running](running.md).

## What `connections` is

A library of primitives for clausal connection tableaux, in two layers.

**`calculus/`** is the transition system: what a state is, what actions exist,
which of them the calculus admits, and what applying one does.

    rules, actions, tableau, state, dynamics

**`run/`** is acting in that system on one problem: building a state from a
problem file, rolling a policy out from it, the strategies that fix which
system and which policy, the schedules that allocate budget across strategies,
and the SZS vocabulary for outcomes.

    problem, rollout, strategy, schedule, result, status

`calculus` knows nothing of budgets, schedules or statuses. `run` knows nothing
of processes or of other problems.

## What `connections` is not

It is not a prover. The named provers are packages: a configuration and a CLI
each.

| | |
|---|---|
| `pycop` | leanCoP-equivalent strategies, parity harness, CLI |
| `satcop` | SAT shadow and `Reset`, CLI |
| `imitation` | learned policies, training, campaigns |

A CLI owns argument parsing, schedule selection, SZS on stdout, and the exit
code.

It also has no runner. Nothing in `connections` starts a process, manages a
pool, or writes a file. `run` takes one problem and returns a `Result`, and
`Result` knows how to serialise itself; selecting problems, spending CPUs on
them, and aggregating what comes back are each package's own business.

## Where the boundary falls

**`connections` stops at one problem.** That is where CASC draws it -- systems
there run "as black boxes, on one problem at a time" -- so the primitive is the
shape every other prover already has.

Above it, decisions differ irreconcilably. A laptop, a 400-core queue and a
mixed Sapphire/Icelake fleet want different answers about how many problems run
at once, what to do with one that will not stop, and whether a killed campaign
resumes. An abstraction over all three is how a scheduling layer grows to 888
lines.

What is genuinely shared is the `Result`, and that is data.

## Packages and dependency edges

```
connections   calculus, run, SZS                        -> lark
pycop         leanCoP-equivalent prover, parity, CLI    -> connections
satcop        SAT shadow, Reset, CLI                    -> connections
imitation     policies, graph model, training, campaigns -> connections, torch
```

`connections` never imports from a package built on it. It is the citable
artefact and stays independently installable.

Four distributions. A fifth earns its place when a second consumer needs the
same thing: `imitation`'s campaign machinery would become one if `satcop`
wanted resumable runs, and not before.

## Documents

| | |
|---|---|
| [dynamics](dynamics.md) | states, actions, transitions, undo |
| [running](running.md) | rollout, strategy, schedule, run, limits, hardware |

The reference documentation under `docs/src/` describes the code as it stands
today, which is not yet this. Where they disagree, these notes are the target.
