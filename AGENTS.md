# AGENTS.md

## Project Context

This repository is undergoing a refactor of a connection-calculus prover toward a cleaner architecture:

- Core logic primitives live in `connections/logic/`
- Search/state/runtime lives in `connections/search/`
- Parsers/factories stay in `connections/utils/`
- Prefixes are first-class syntax via `Prefix(parts: tuple[Term, ...])`
- Term substitution (`sigma_q`) and prefix substitution (`sigma_p`) are conceptually separate

---

## Current Architecture (as of now)

### Search layer

- Canonical state implementation is now in `connections/search/state.py`
- Environment is in `connections/search/env.py`
- Action model is in `connections/search/actions.py`
- `classical.py` was removed; `state.py` is now the source of truth

### Logic layer

- Syntax: `connections/logic/syntax.py`
  - No shared `Expression` base anymore
  - `Term`, `Literal`, `Prefix` are separate
- Term substitution logic: `connections/logic/substitution.py`
- Prefix logic is centralized in: `connections/logic/prefix_substitution.py`
- Tableau model: `connections/logic/tableau.py`

### Factories/parsers

- Factories/interner/freshening: `connections/utils/factories.py`
- CNF parsing: `connections/utils/cnf_parsing.py`
- ICNF parsing: `connections/utils/icnf_parsing.py`

---

## Prefix Representation and Semantics

- Old `Function("string", ...)` prefix representation has been removed from active code paths.
- Prefixes are represented as:
  - `Prefix(parts: tuple[Term, ...])`
- Prefix logic dispatch depends on:
  - `logic` (`classical`, `intuitionistic`, `D`, `T`, `S4`, `S5`)
  - `domain` (`constant`, `cumulative`, `varying`)

---

## Search/State Notes

- `State` currently stores:
  - `matrix`
  - `tableau`
  - term substitution object (currently class `Substitution` in `logic/substitution.py`)
  - prefix substitution object (`PrefixSubstitution`)
- Action generation is read-only; transitions happen in `update_goal(...)`.
- Prefix checks are delegated to `PrefixSubstitution`:
  - relation checks during extension/reduction
  - admissibility/proof pair unification for non-classical closure checks

---

## Factory/Fresh Variable Notes

- Prefix fresh variables are generated via factory now:
  - `VarFactory` in `connections/utils/factories.py`
- `State` uses `self.prefix_var_factory.fresh("W")`
- `ClauseFactory.freshen_clause(...)` now takes a `Clause` (not raw list/iterable of literals)

---

## Tests Status

Recent focused suite run passed:

- `tests/test_prefix_substitution.py`
- `tests/test_cnf_parsing.py`
- `tests/test_unification.py`
- `tests/test_classical.py`
- `tests/test_intuitionistic.py`
- `tests/test_primitives.py`

Result in recent run: all passing.

---

## Immediate Planned Refactor (next)

### Rename and composition plan

- Rename term substitution class:
  - `Substitution` -> `TermSubstitution`
- Introduce common substitution protocol/interface for composition:
  - shared API for update/cut/find/unify/can_unify/to_dict/equal
- Make `PrefixSubstitution.bindings` authoritative (stateful, like term substitution)
  - support scoped updates and rollback like term substitution
- Add compositional wrapper (or clear paired usage) for `sigma_q` + `sigma_p`
- Update `State` to use explicit term/prefix substitution objects consistently

---

## Paper References (working set)

These are the papers currently used as primary reference material (local Zotero links):

1. Otten (2014), *MleanCoP: A Connection Prover for First-Order Modal Logic*
   `/Users/fredrik/Zotero/storage/35YSWHFY/Otten - 2014 - MleanCoP A Connection Prover for First-Order Moda.pdf`

2. Wallen (1996), *unify_tab96*
   `/Users/fredrik/Zotero/storage/FVU96AXW/unify_tab96.pdf`

3. Otten (2023), *20 Years of leanCoP - An Overview of the Provers*
   `/Users/fredrik/Zotero/storage/QTWHV5ZU/Otten - 2023 - 20 Years of leanCoP - An Overview of the Provers.pdf`

4. Otten (2008), *leanCoP 2.0 and ileanCoP 1.2 High Performance Lean Theorem Proving in Classical and Intuitionistic Logic*
   `/Users/fredrik/Zotero/storage/PAG4LVNT/Otten - 2008 - leanCoP 2.0 and ileanCoP 1.2 High Performance Lea.pdf`

---

## Working Principles / Constraints

- Keep scope tight.
- Prefer immutable syntax.
- Avoid compatibility layers unless explicitly requested.
- Keep parser/factory logic in `utils`, core logic in `logic`, runtime state/search in `search`.
- Prefix logic should live in `PrefixSubstitution`.
- Avoid class-hierarchy-heavy design when a dispatch-based approach is enough.
