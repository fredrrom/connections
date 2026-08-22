"""Known ID overclaims: the path-limit condition undercounts blocked candidates.

Two m2k problems where leanCoP proves Theorem but our ID agent claims a fixed
point under cut+comp(7). Instrumentation (2026-08-22) shows the flag lifecycle
is correct through the comp switch: depths 1..6 record path-limit hits, then at
depth_limit=7 in complete mode the agent detects zero gate-blocked unifiable
candidates and stops, while the reference at the same point still finds blocked
candidates (a third pathlim_hit at trace event 163 that native never emits) and
deepens to a proof.

So the divergence is in which candidates reach the depth gate at the limit
boundary, not in the flag reset. Until that is fixed, these two problems
produce an unsound CounterSatisfiable. The scut/cut variants of the same
problems are already honest GaveUp via the warrant gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from connections.run import Problem, run
from connections.run.strategy import StrategySchedule
from connections.run.szs import SZSStatus

pycop = pytest.importorskip("pycop")
from pycop import LeancopSettingsCodec  # noqa: E402

M2K = Path("/Users/fredrik/dev/phd/benchmarks/m2k")

WITNESSES = ["t100_relat_1", "t10_enumset1"]


@pytest.mark.parametrize("name", WITNESSES)
@pytest.mark.xfail(
    reason="ID pathlim search undercounts blocked candidates at the limit",
    strict=True,
)
def test_witness_is_not_counter_satisfiable(name):
    problem = M2K / f"{name}.p"
    if not problem.exists():
        pytest.skip("m2k corpus not present")
    strategy = LeancopSettingsCodec.from_tokens(["cut", "comp(7)"])
    result = run(
        Problem(problem),
        schedule=StrategySchedule.single(strategy, steps=20000, timeout_seconds=10.0),
    )
    assert result.szs_status is not SZSStatus.COUNTER_SATISFIABLE
