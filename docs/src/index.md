# Connections

`connections` provides classical, intuitionistic, and modal connection-tableaux
construction primitives for proof-search control. Version
0.1 focuses on a clean prover core, reusable symbolic policies, native matrix
construction, `pycop`, and local diagnostics against leanCoP-family reference
provers.

## Docs

- [Prover API](prover-api.md)
- [State and Dynamics](state-dynamics.md)
- [Unification and Constraints](unification.md)
- [TPTP Parser](tptp-parser.md)
- [Corpus and Parity Tools](corpus-and-parity-tools.md)

## 0.1 Boundary

The public boundary is the concrete `Prover` loop, reusable symbolic policies,
strategy schedules, tableau state/dynamics, and SZS result reporting.
