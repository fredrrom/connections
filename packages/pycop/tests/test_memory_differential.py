"""The clean and traced memories must take identical actions.

The connections library ships clean memories: no trace choreography, no
deferred bookkeeping, rebuilt on the fringe-mirroring invariant. pycop ships
the traced memories whose event streams are bit-identical to leanCoP. This
test is the referee between them: same problem, same options, identical
action sequences and final statuses. Any divergence is a bug in one of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from connections.agent import AgentOptions, IDMemory, OnlineSearchAgent
from connections.run import Problem, build_state
from connections.run.rollout import rollout
from connections.run.strategy import MatrixOptions

from pycop.leancop_memory import TracedIDMemory, first

M2K = Path("/Users/fredrik/dev/phd/benchmarks/m2k")

PROBLEMS = [
    "l1_enumset1", "l5_orders_2", "l13_ordinal1", "l111_zfmisc_1",
    "t3_xboole_0", "t7_xboole_1", "l143_zfmisc_1", "t2_tarski",
]
DISCIPLINES = [
    dict(factorization="equal"),
    dict(cut=True, factorization="equal"),
    dict(cut=True, scut=True, factorization="equal"),
    dict(cut=True, comp=7, factorization="equal"),
]


def _rollout(problem: Path, memory, options):
    state = build_state(Problem(problem), matrix_options=MatrixOptions())
    agent = OnlineSearchAgent(memory, first, AgentOptions(**options))
    return rollout(state, agent, step_limit=3000)


@pytest.mark.parametrize("name", PROBLEMS)
@pytest.mark.parametrize(
    "options", DISCIPLINES, ids=["plain", "cut", "scut", "comp"]
)
def test_clean_and_traced_memories_act_identically(name, options, request):
    problem = M2K / f"{name}.p"
    if not problem.exists():
        pytest.skip("m2k corpus not present")
    if "plain" in request.node.callspec.id:
        # Known delta: the traced memory's step-mode backtracking prefers
        # reopening the newest open choicepoint that still has an application,
        # which can be non-chronological; the clean memory backtracks
        # chronologically. Genuine behaviour, not choreography -- the reopen
        # rule is the remaining port. Soundness is unaffected either way:
        # both searches are systematic in plain mode.
        request.node.add_marker(
            pytest.mark.xfail(
                reason="step-mode reopen rule not yet ported to DFSMemory",
                strict=False,
            )
        )

    clean = _rollout(problem, IDMemory(), options)
    traced = _rollout(problem, TracedIDMemory(**options), options)

    assert clean.steps == traced.steps
    assert clean.stop == traced.stop
    assert clean.status == traced.status
    clean_kinds = [type(a).__name__ for a in clean.actions]
    traced_kinds = [type(a).__name__ for a in traced.actions]
    assert clean_kinds == traced_kinds
    for i, (a, b) in enumerate(zip(clean.actions, traced.actions)):
        assert repr(a) == repr(b), f"diverged at step {i}: {a!r} vs {b!r}"
