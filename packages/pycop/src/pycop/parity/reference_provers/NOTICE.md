# Third-party reference provers

This directory bundles the leanCoP-family provers that the parity harness uses
as correctness oracles. They are **not** part of `pycop`'s or `connections`'
own source. They are included so that parity results are reproducible against a
fixed reference rather than whatever happens to be installed.

All of them are by **Jens Otten** and distributed under the **GNU General
Public License**. `pycop` and `connections` are GPL-3.0-or-later, so
redistribution here is compatible; see `LICENSE` in the repository root for the
license text.

Upstream for all three: <https://www.leancop.de>

## leanCoP 2.1

Classical first-order logic. <https://www.leancop.de>

Copyright (c) 1999-2022 by Jens Otten. GNU General Public License.

    prolog/leancop21/
        leancop21.pl          core prover (ECLiPSe)
        leancop21_swi.pl      SWI-Prolog variant          [modified, see below]
        leancop21_sic.pl      SICStus variant
        def_mm.pl             clausal form transformation
        leancop_main.pl       prover entry point
        leancop_main_trans.pl translation entry point
        leancop_proof.pl      proof presentation
        leancop_tptp2.pl      TPTP syntax translation
        leancop.sh            invocation script
        ReadMe_leancop        upstream ReadMe

## ileanCoP 1.2

Intuitionistic first-order logic. <https://www.leancop.de/ileancop/>

Copyright (c) 2005-2022 by Jens Otten. GNU General Public License.

    prolog/ileancop12/
        ileancop12.pl          core prover               [modified, see below]
        def_mm_intu.pl         intuitionistic clausal form [modified, see below]
        leancop_main_itrans.pl translation entry point
        leancop_tlimit.pl      time-limited invocation
        leancop_tptp2.pl       TPTP syntax translation
        format.leancop         TPTP2X format file
        ileancop.sh            invocation script
        ReadMe_ileancop        upstream ReadMe

## MleanCoP 1.3

First-order modal logics D, T, S4, S5 with constant, cumulative or varying
domains. <https://www.leancop.de/mleancop/>

Copyright (c) 2009-2023 by Jens Otten. GNU General Public License.

    prolog/mleancop13/
        mleancop13.pl          core prover (ECLiPSe)
        mleancop13_swi.pl      SWI-Prolog variant        [modified, see below]
        mleancop13_sic.pl      SICStus variant
        mleancop_defmm.pl      modal clausal form transformation
        mleancop_main.pl       prover entry point
        leancop_main_mtrans.pl translation entry point
        mleancop_tptp2.pl      modal TPTP syntax translation
        nanocop_qmltp2.pl      QMLTP syntax translation
        mleancop.sh            invocation script
        ReadMe_mleancop        upstream ReadMe

## Modifications

Four files carry changes made for this project, between 2023 and 2026. Each
modified file states its changes in a header block. In summary:

| file | change |
|---|---|
| `leancop21/leancop21_swi.pl` | trace mode and choice tracing, step budgets, `lit_trace/4` source metadata, marker-literal handling |
| `ileancop12/ileancop12.pl` | trace mode and choice tracing, step budgets, marker-literal handling, `def_mm_intu_f` behaviour merged into `def_mm_intu.pl` |
| `mleancop13/mleancop13_swi.pl` | trace mode and choice tracing, step budgets, marker-literal handling |
| `ileancop12/def_mm_intu.pl` | former `def_mm_intu_f` changes merged in |

The modifications exist so that a reference run emits the same search events the
native prover does, which is what makes trace parity checkable at all. They add
instrumentation and do not change the search these provers perform.

Everything else in these directories is unmodified upstream.

**Do not edit these files further.** Local SWI-Prolog compatibility adapters
belong in `pycop/parity/prolog/` instead, alongside `swi_compat.pl` and
`matrix_dump.pl`.

## Citing

If you are citing the reference provers rather than this software, cite Otten's
papers for the respective systems rather than this repository. `CITATION.cff` in
the repository root covers `connections` only.
