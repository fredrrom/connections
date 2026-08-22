# Development

```bash
uv sync --dev --group docs
```

## Normal checks

Run these before sending changes:

```bash
uv run pytest tests
uv run --package pycop pytest packages/pycop/tests
uv run ruff check .
uv run ty check
uv build
uv run --group docs mkdocs build --strict -f docs/mkdocs.yml
```

None of them need SWI-Prolog or an external benchmark corpus. The parity
diagnostics that do are developer tools, not normal checks -- see
[pycop](../packages/pycop.md).

## Workspace layout

```
connections/            workspace root, and the `connections` distribution
├── pyproject.toml      [tool.uv.workspace] members = ["packages/*"]
├── uv.lock             one lockfile, root only
├── docs/               this site
├── src/connections/    the library
└── packages/
    └── pycop/          leanCoP-equivalent prover, parity, CLI
```

Every member repeats the same shape: its own `pyproject.toml`, its own
`src/<name>/`, its own `tests/`. The root never depends on a member, which is
what keeps `connections` independently installable.

Run one member's tests directly:

```bash
uv run --package pycop pytest packages/pycop/tests
```

## Documentation

Source lives under `docs/src/`, configured by `docs/mkdocs.yml`.

```bash
uv run --group docs mkdocs serve -f docs/mkdocs.yml    # http://127.0.0.1:8000/
uv run --group docs mkdocs build --strict -f docs/mkdocs.yml
```

GitHub Pages builds from `docs/mkdocs.yml` via `.github/workflows/pages.yml`.

Three kinds of page, kept apart because they go stale at different rates:

- **Design** notes argue, and describe the target. They are hand-written and are
  the place to settle a boundary.
- **Guides** are task-shaped and short.
- **Reference** is generated from docstrings. Do not hand-write it; fix the
  docstring instead.

Where the design notes and the code disagree, the notes are the target. That
gap is expected and is called out where it matters.

## Artifacts

Corpus rows, profiles and parity output go under `artifacts/`, which is
gitignored.

## Notation

Design notes use the notation of the inter-conjecture paper, so that this site
and the dissertation name the same objects the same way: *P(M)* for the
transition system, *A(s)* for the enabled actions, *A(s, μ)* for what a policy's
memory exposes, *(π_mem, U_π)* for a stateful policy. The correspondence table
between these notes and the dissertation chapters lives in that repository's
`docs/thesis-map.md`.

A claim that survives rewriting the code in another language belongs to the
dissertation. A claim naming a module, a signature, or a known gap belongs here.
