"""Former ID overclaims, kept as regressions.

Two m2k problems where leanCoP proves Theorem but the old frame-stack ID
agent claimed a fixed point under cut+comp(7): its path-limit condition
undercounted blocked candidates at the limit boundary. The rewrite of the
search agents onto per-goal alternatives with abandon-and-regenerate
backtracking (2026-08-23) fixed the undercount, so these are now plain
assertions that the unsound CounterSatisfiable never comes back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from connections.interaction import Problem, run_schedule
from connections.interaction.strategy import StrategySchedule
from connections.interaction.szs import SZSStatus

pycop = pytest.importorskip("pycop")
from pycop import LeancopSettingsCodec  # noqa: E402

M2K = Path("/Users/fredrik/dev/phd/benchmarks/m2k")

WITNESSES = ["t100_relat_1", "t10_enumset1"]


@pytest.mark.parametrize("name", WITNESSES)
def test_witness_is_not_counter_satisfiable(name):
    problem = M2K / f"{name}.p"
    if not problem.exists():
        pytest.skip("m2k corpus not present")  # ty: ignore[invalid-argument-type, too-many-positional-arguments]
    strategy = LeancopSettingsCodec.from_tokens(["cut", "comp(7)"])
    result = run_schedule(
        Problem(problem),
        schedule=StrategySchedule.single(strategy, steps=20000, timeout_seconds=10.0),
    )
    assert result.szs_status is not SZSStatus.COUNTER_SATISFIABLE
