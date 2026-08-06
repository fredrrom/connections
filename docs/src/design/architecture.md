# Architecture

This repository is a uv workspace. `connections` is the library; the packages
under `packages/` are built on it. This note is the map. The transition system
is described in [dynamics](dynamics.md), and everything from a rollout up to
running a corpus in [running](running.md).

## What `connections` is

A library of primitives for clausal connection tableaux, in four groups.

**The language** -- what a problem is, and how to read one.

    syntax          terms, literals, clauses, matrices
    parsing         TPTP text to formulas
    clausification  formulas to a matrix

**Constraints** -- what makes a connection admissible.

    constraints     unification, rigid substitutions, prefixes

**The calculus** -- the transition system a policy acts in.

    calculus        state, tableau, actions, rules, dynamics

**Acting in it** -- one problem at a time.

    policy          choosing among admissible actions
    run             build_state, rollout, strategy, schedule, result, status

Dependencies run upward: `constraints` and `parsing` over `syntax`,
`clausification` over `parsing`, `calculus` over `syntax` and `constraints`,
`policy` over `calculus`, and `run` over all of it. Nothing below `run` knows
about budgets, schedules or statuses; nothing below `policy` knows a policy
exists.

!!! note "Two cycles today"

    `syntax` reaches into `constraints` from inside `Matrix`, which filters a
    literal's candidate complements by static unifiability -- a deferred import
    working around a real cycle. Deciding which literals can connect is a
    calculus question, so the filter belongs above `syntax`.

    `policy` imports `actions`, `state`, `dynamics`, `rules` and `status` from
    `prover`, which imports `policy` back. Every one of those is a calculus
    thing, so splitting `prover` into `calculus` and `run` dissolves this one
    on its own.

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
