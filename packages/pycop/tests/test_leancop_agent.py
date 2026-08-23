"""leanCoP as OnlineIDAgent with the first chooser, against real states."""

from __future__ import annotations

from pathlib import Path

import pytest

from connections.agent import AgentStatus
from connections.agent.id import OnlineIDAgent
from connections.environment.actions import ApplyAction, UndoAction
from connections.environment.rules import Start
from connections.environment.state import State
from connections.environment.tableau import Tableau
from connections.interaction import (
    MatrixOptions,
    Problem,
    SZSStatus,
    StrategySchedule,
    build_state,
    rollout,
    run_schedule,
)
from connections.syntax.matrix import Matrix, Clause
from connections.trace_logging import TRACE_LEVEL
from pycop.leancop import first, leancop_agent
from pycop.settings_codec import LeancopSettingsCodec

PROVABLE = """
fof(all_men_mortal, axiom, ![X]: (man(X) => mortal(X))).
fof(socrates_man, axiom, man(socrates)).
fof(goal, conjecture, mortal(socrates)).
"""

UNPROVABLE = """
fof(socrates_man, axiom, man(socrates)).
fof(goal, conjecture, mortal(socrates)).
"""

DEEP = """
fof(trans, axiom, ![X, Y, Z]: ((le(X, Y) & le(Y, Z)) => le(X, Z))).
fof(ab, axiom, le(a, b)).
fof(bc, axiom, le(b, c)).
fof(goal, conjecture, le(a, c)).
"""


def _problem(tmp_path: Path, text: str) -> Problem:
    path = tmp_path / "problem.p"
    path.write_text(text)
    return Problem(path)


def _run(tmp_path: Path, text: str, settings: list[str]):
    strategy = LeancopSettingsCodec.from_tokens(settings)
    return run_schedule(
        _problem(tmp_path, text),
        schedule=StrategySchedule.single(strategy, steps=20_000),
    )


def _state(tmp_path: Path, text: str) -> State:
    return build_state(_problem(tmp_path, text), matrix_options=MatrixOptions())


def test_leancop_agent_is_the_id_agent_with_first():
    agent = leancop_agent(cut=True, scut=True, comp=7, factorization="equal")
    assert isinstance(agent, OnlineIDAgent)
    assert agent.choose is first
    assert agent.options.cut and agent.options.scut
    assert agent.options.comp == 7
    assert agent.options.factorization == "equal"


def test_first_returns_the_first_action():
    state = State(matrix=Matrix(()), tableau=Tableau())
    head = UndoAction(1)
    assert first(state, [head, UndoAction(2)]) is head


def test_rejects_nonpositive_initial_depth():
    with pytest.raises(ValueError, match="at least 1"):
        leancop_agent(initial_depth=0)


@pytest.mark.parametrize(
    "settings",
    [[], ["cut"], ["cut", "scut"], ["cut", "comp(7)"], ["conj", "cut"]],
    ids=["plain", "cut", "scut", "comp", "conj"],
)
def test_proves_the_provable_problem(tmp_path, settings):
    result = _run(tmp_path, PROVABLE, settings)
    assert result.szs_status is SZSStatus.THEOREM


def test_plain_settings_refute_the_unprovable_problem(tmp_path):
    result = _run(tmp_path, UNPROVABLE, [])
    assert result.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert result.strategy_results[0].agent_status is AgentStatus.ID_FIXED_POINT


def test_cut_forfeits_the_refutation_claim(tmp_path):
    result = _run(tmp_path, UNPROVABLE, ["cut"])
    assert result.szs_status is SZSStatus.GAVE_UP
    assert result.strategy_results[0].agent_status is AgentStatus.GAVE_UP


def test_depth_ladder_traces_pathlim(tmp_path, caplog):
    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    result = _run(tmp_path, DEEP, [])
    assert result.szs_status is SZSStatus.THEOREM
    assert "pathlim" in caplog.messages


def test_scut_restricts_the_start_and_traces(tmp_path, caplog):
    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    result = _run(tmp_path, PROVABLE, ["scut", "cut"])
    assert result.szs_status is SZSStatus.THEOREM
    assert "scut" in caplog.messages
    assert "cut" in caplog.messages


def test_agent_status_closed_after_proof(tmp_path):
    state = _state(tmp_path, PROVABLE)
    agent = leancop_agent(factorization="equal")
    attempt = rollout(state, agent, step_limit=10_000)
    assert attempt.status is AgentStatus.CLOSED
    assert state.tableau.root.closed


def test_agent_resets_on_a_fresh_episode(tmp_path):
    agent = leancop_agent(comp=1, cut=True, factorization="equal")
    state = _state(tmp_path, UNPROVABLE)
    rollout(state, agent, step_limit=10_000)
    assert agent.options.comp is None  # the comp switch mutated the options
    probe = _state(tmp_path, PROVABLE)
    agent(probe)  # the episode boundary restores the constructed options
    assert agent.options.comp == 1
    attempt = rollout(_state(tmp_path, PROVABLE), agent, step_limit=10_000)
    assert attempt.status is AgentStatus.CLOSED


def test_initial_depth_is_honoured(tmp_path):
    state = _state(tmp_path, PROVABLE)
    agent = leancop_agent(initial_depth=3, factorization="equal")
    agent(state)
    assert agent.depth_limit == 3


def test_empty_matrix_reaches_a_fixed_point(caplog):
    state = State(matrix=Matrix(()), tableau=Tableau())
    agent = leancop_agent(scut=True, comp=3, factorization="equal")
    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    action = agent(state)
    assert action is None
    assert agent.status is AgentStatus.ID_FIXED_POINT
    assert caplog.messages == ["pathlim", "pathlim"]


def test_real_empty_clause_is_kept_as_start_action(caplog):
    state = State(matrix=Matrix((Clause(()),)), tableau=Tableau())
    agent = leancop_agent(scut=True, comp=3, factorization="equal")
    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    action = agent(state)
    assert isinstance(action, ApplyAction)
    assert isinstance(action.rule, Start)
    assert action.rule.clause.literals == ()
    assert caplog.messages == ["scut"]
