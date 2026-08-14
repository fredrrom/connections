"""The rollout primitive: a policy acting in P(M) until something stops it."""

from __future__ import annotations

import time

from connections.calculus.actions import ApplyAction, UndoAction
from connections.calculus.outcome import ProverOutcome
from connections.calculus.problem import Problem
from connections.calculus.state import State
from connections.calculus.tableau import Tableau
from connections.policy import Policy
from connections.run.rollout import Rollout, rollout

from tests.unit.run.test_prover import _non_theorem_matrix


def _state():
    return State(
        problem=Problem(matrix=_non_theorem_matrix(), start_clauses="positive"),
        tableau=Tableau(),
    )


class _Scripted(Policy):
    """Yields each scripted decision in turn, then nothing."""

    def __init__(self, decisions=()):
        self.decisions = list(decisions)
        self.calls = 0
        self.closed_notifications = 0

    def __call__(self, state):
        self.calls += 1
        return self.decisions.pop(0) if self.decisions else None

    def on_tableau_closed(self, state):
        self.closed_notifications += 1


def test_a_policy_call_yielding_no_action_is_not_a_step():
    policy = _Scripted()

    result = rollout(_state(), policy=policy)

    assert isinstance(result, Rollout)
    assert result.actions == ()
    assert result.steps == 0
    assert result.inference_steps == 0
    assert result.outcome is None
    assert policy.calls == 1, "the policy was still consulted"


def test_a_policy_outcome_is_reported_verbatim():
    policy = _Scripted([ProverOutcome.DFS_EXHAUSTED])

    result = rollout(_state(), policy=policy)

    assert result.outcome is ProverOutcome.DFS_EXHAUSTED
    assert result.steps == 0


def test_exhausted_step_budget_stops_before_consulting_the_policy():
    policy = _Scripted()

    result = rollout(_state(), policy=policy, step_limit=0)

    assert result.outcome is ProverOutcome.STEP_BUDGET
    assert result.steps == 0
    assert policy.calls == 0


def test_expired_deadline_stops_before_consulting_the_policy():
    policy = _Scripted()

    result = rollout(_state(), policy=policy, deadline=time.monotonic() - 1.0)

    # An allotment the rollout notices itself is ResourceOut, not Timeout:
    # Timeout is a claim about a process, made by whatever supervises it.
    assert result.outcome is ProverOutcome.TIME_BUDGET
    assert result.steps == 0
    assert policy.calls == 0


def test_steps_and_deadline_are_checked_at_the_same_point():
    """Both budgets are an allotment that ran out; steps is checked first."""
    policy = _Scripted()

    result = rollout(
        _state(),
        policy=policy,
        step_limit=0,
        deadline=time.monotonic() - 1.0,
    )

    assert result.outcome is ProverOutcome.STEP_BUDGET


def test_the_rollout_returns_the_state_it_acted_on():
    state = _state()

    result = rollout(state, policy=_Scripted())

    assert result.state is state, "the state is mutated in place, not copied"


def test_counts_are_derived_from_the_recorded_actions():
    """steps and inference_steps cannot disagree with `actions`, by construction."""
    append = object.__new__(ApplyAction)
    prune = object.__new__(UndoAction)

    result = Rollout(actions=(append, prune, append), state=None, outcome=None)

    assert result.steps == 3, "every action is one application of T"
    assert result.inference_steps == 2, "only appends are inference steps"
    assert result.inference_steps <= result.steps


def test_proved_is_derived_from_the_outcome():
    proved = Rollout(actions=(), state=None, outcome=ProverOutcome.PROVED)
    budget = Rollout(actions=(), state=None, outcome=ProverOutcome.STEP_BUDGET)

    assert proved.proved
    assert not budget.proved


def test_both_in_rollout_budgets_are_resource_out_not_timeout():
    """The layers split by vocabulary, so they cannot contradict each other."""
    from connections.run.szs import SZSStatus, to_szs_status

    for outcome in (ProverOutcome.STEP_BUDGET, ProverOutcome.TIME_BUDGET):
        assert to_szs_status(outcome, has_conjecture=True) is SZSStatus.RESOURCE_OUT
