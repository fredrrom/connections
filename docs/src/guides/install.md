# Install

This repository is a [uv](https://docs.astral.sh/uv/) workspace. `connections`
is the library at the root; the provers and learning code are members under
`packages/`.

## From a checkout

```bash
git clone https://github.com/fredrrom/connections
cd connections
uv sync
```

`uv sync` resolves the whole workspace against the single root `uv.lock`, so
every member sees the same versions.

For development work, add the groups:

```bash
uv sync --dev --group docs
```

## Just the library

`connections` is published independently of anything built on it, and depends
only on `lark`:

```bash
uv add connections
```

Nothing in the library starts a process, manages a pool, or writes a file, so
installing it commits you to nothing about how you run problems. See
[running](../design/running.md) for where that boundary falls and why.

## A package

Members declare the library through the workspace:

```toml
# packages/pycop/pyproject.toml
dependencies = ["connections"]

[tool.uv.sources]
connections = { workspace = true }
```

Working on one member does not require installing the others.

## Python

`connections` requires Python 3.10 or later. Members may be narrower --
`imitation` needs 3.12 or later because of its model dependencies.

## Optional external tools

Neither is needed for the normal checks:

- **SWI-Prolog** (`swipl` on `PATH`) for the parity diagnostics in
  [pycop](../packages/pycop.md), which compare against bundled leanCoP-family
  reference provers.
- **A benchmark corpus** such as TPTP for corpus runs. Nothing reads a corpus
  path from the environment; see [language](../design/language.md) on source
  resolution.
