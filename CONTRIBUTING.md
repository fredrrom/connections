# Contributing

`connections` provides classical, intuitionistic, and modal connection-tableaux
construction primitives for proof-search control. It
includes `pycop` support for leanCoP 2.1, iLeanCoP 1.3, and mLeanCoP 1.2
behavior inside the same prover, policy, state, and dynamics framework.

## Development Setup

Use `uv` for local development.

The development workflow, normal checks, documentation commands, parity
diagnostics, corpus runners, and profiling commands are documented in
[`docs/src/development.md`](docs/src/development.md).

The fast local checks are:

```bash
uv run pytest tests
uv run ruff check .
uv run ty check
uv build
uv run --group docs mkdocs build --strict -f docs/mkdocs.yml
```

Do not edit the bundled Prolog reference provers under
`tools/parity/reference_provers/`. Local SWI-Prolog compatibility adapters
belong under `tools/parity/prolog/`.

## Release Checklist

Use the relevant `CHANGELOG.md` section as the GitHub release body. Do not tag
or publish a release until the release checklist has been run and reviewed.
