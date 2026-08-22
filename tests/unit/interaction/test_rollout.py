"""The rollout primitive: the bare agent-environment loop."""

from __future__ import annotations

import time

import pytest

from connections.agent import Agent, AgentStatus
from connections.env.state import State
from connections.env.tableau import Tableau
from connections.interaction.records import Rollout
from connections.interaction.truncation import Truncation
from connections.interaction.rollout import rollout

from tests.unit.interaction.test_run import _non_theorem_matrix


def _state():
    return State(matrix=_non_theorem_matrix(), tableau=Tableau())


class _Scripted(Agent):
    """Yields each scripted action in turn, then nothing."""

    def __init__(self, actions=(), status=AgentStatus.GAVE_UP):
        super().__init__()
        self.script = list(actions)
        self.calls = 0
        self.states_seen = []
        self.status = status

    def __call__(self, state):
        self.calls += 1
        self.states_seen.append(state)
        return self.script.pop(0) if self.script else None


def test_an_agent_with_no_action_stops_the_rollout():
    agent = _Scripted()

    result = rollout(_state(), agent)

    assert isinstance(result, Rollout)
    assert result.truncation is None
    assert result.status is AgentStatus.GAVE_UP
    assert result.actions == ()
    assert result.steps == 0
    assert agent.calls == 1, "the agent was still consulted"


def test_the_status_is_the_agents_word_queried_once():
    agent = _Scripted(status=AgentStatus.DFS_EXHAUSTED)

    result = rollout(_state(), agent)

    assert result.truncation is None
    assert result.status is AgentStatus.DFS_EXHAUSTED


def test_exhausted_step_budget_stops_before_consulting_the_agent():
    agent = _Scripted()

    result = rollout(_state(), agent, step_limit=0)

    assert result.truncation is Truncation.STEPS
    assert result.status is None, "budget stops never consult the agent"
    assert result.steps == 0
    assert agent.calls == 0


def test_expired_deadline_stops_before_consulting_the_agent():
    agent = _Scripted()

    result = rollout(_state(), agent, deadline=time.monotonic() - 1.0)

    assert result.truncation is Truncation.TIME
    assert result.status is None
    assert agent.calls == 0


def test_steps_and_deadline_are_checked_at_the_same_point():
    agent = _Scripted()

    result = rollout(
        _state(),
        agent,
        step_limit=0,
        deadline=time.monotonic() - 1.0,
    )

    assert result.truncation is Truncation.STEPS


def test_the_rollout_returns_the_state_it_acted_on():
    state = _state()

    result = rollout(state, _Scripted())

    assert result.state is state, "the state is mutated in place, not copied"


def test_unrecorded_rollouts_still_count_steps():
    agent = _Scripted()

    result = rollout(_state(), agent, record=False)

    assert result.actions is None
    assert result.steps == 0


def test_recorded_actions_must_agree_with_the_step_count():
    with pytest.raises(ValueError):
        Rollout(state=None, status=AgentStatus.GAVE_UP, truncation=None, actions=(), steps=3)


def test_the_rollout_never_reads_the_tableau():
    """The loop is generic: closure is the agent's to observe, the judge's to
    verify. A state with no tableau at all rolls out fine."""

    class _NoTableau:
        pass

    agent = _Scripted()

    result = rollout(_NoTableau(), agent)

    assert result.truncation is None
    assert agent.states_seen and isinstance(agent.states_seen[0], _NoTableau)
