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

    agent           choosing among admissible actions; memories and choosers
    run             build_state, rollout, strategy, schedule, result, judge

Dependencies run upward: `constraints` and `parsing` over `syntax`,
`clausification` over `parsing`, `calculus` over `syntax` and `constraints`,
`agent` over `calculus`, and `run` over all of it. Nothing below `run` knows
about budgets, schedules or statuses; nothing below `agent` knows an agent
exists.

The R&N learning-agent architecture maps onto the layers directly:

| R&N | here |
|---|---|
| environment | *P(M)*, the calculus |
| performance element | the agent: percept in, action out |
| critic | the judge in `run`: verdicts from outside the agent |
| learning element | the `imitation` package |
| problem generator | the schedule (one problem) and the corpus sampler (many) |

!!! note "One cycle today"

    `syntax` reaches into `constraints` from inside `Matrix`, which filters a
    literal's candidate complements by static unifiability -- a deferred import
    working around a real cycle. Deciding which literals can connect is a
    calculus question, so the filter belongs above `syntax`.

    The `policy`/`prover` cycle is gone. Everything `policy` imported from
    `prover` was a calculus thing, so splitting `prover` into `calculus` and
    `run` dissolved it without further work.

## What `connections` is not

It is not a prover. The named provers are in packages: a configuration and a CLI each.

| | |
|---|---|
| `pycop` | leanCoP-equivalent strategies, parity harness, CLI |
| `imitation` | learned policies, training, campaigns |

A CLI owns argument parsing, schedule selection, SZS on stdout, and the exit
code.

It also has no runner. Nothing in `connections` starts a process, manages a
pool, or writes a file. `run` takes one problem and returns a `Result`, and
`Result.to_dict` serialises it; selecting problems, spending CPUs on
them, and aggregating what comes back are each package's own business.

## Packages and dependency edges

```
connections   calculus, run, SZS                         -> lark
pycop         leanCoP-equivalent prover, parity, CLI     -> connections
imitation     policies, graph model, training, campaigns -> connections, torch
```

`connections` never imports from a package built on it. 

## Documents

One note per group, plus this map.

| | |
|---|---|
| [language](language.md) | source file to matrix: syntax, parsing, clausification |
| [constraints](constraints.md) | what makes a connection admissible |
| [dynamics](dynamics.md) | states, actions, transitions, undo |
| [running](running.md) | rollout, strategy, schedule, run, limits, SZS |

These describe the target. The [API reference](../reference/index.md) is
generated from docstrings and describes the code as it stands, which is not yet this; where they disagree, these notes are the intent.


