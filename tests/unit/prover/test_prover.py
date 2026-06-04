from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

import connections.prover.prover as prover_module
from connections.core.formula import Atom
from connections.core.matrix import Clause, Literal, Matrix
from connections.core.status import ProverOutcome, SZSStatus
from connections.policy import DFSOptions, Policy
from connections.prover.actions import Action
from connections.prover.actions import ActionChoice
from connections.prover.dynamics import Dynamics
from connections.prover.prover import (
    Prover,
    ProverHook,
    ProverTimeoutError,
    StrategyResult,
)
from connections.prover.state import State
from connections.prover.strategy import MatrixOptions, StrategySchedule, WeightedStrategy
from connections.pycop.policy import PycopPolicy
from connections.pycop.strategy import PycopStrategy


def _lit(name: str, *, neg: bool = False) -> Literal:
    return Literal(atom=Atom(name), polarity=not neg)


def _theorem_matrix() -> Matrix:
    return Matrix(
        (
            Clause((_lit("p"),)),
            Clause((_lit("p", neg=True),), role="conjecture"),
        )
    )


def _non_theorem_matrix() -> Matrix:
    return Matrix(
        (
            Clause((_lit("p"),)),
            Clause((_lit("q", neg=True),), role="conjecture"),
        )
    )


class _FirstRulePolicy(Policy):
    def available_actions(self, state: State) -> tuple[Action, ...]:
        for goal in state.fringe:
            actions = Dynamics.apply_actions(state, goal).ordered()
            if actions:
                return actions
        return ()

    def next_action(self, state: State, actions: tuple[Action, ...]) -> Action:
        return self.choose(actions, 0)

    def no_action(self, state: State):
        return None


class _NoActionPolicy(_FirstRulePolicy):
    def available_actions(self, state: State) -> tuple[Action, ...]:
        return ()


@dataclass(frozen=True, slots=True)
class _TestStrategy:
    matrix: MatrixOptions = MatrixOptions()
    policy_kind: str = "first"

    def create_policy(self) -> Policy:
        if self.policy_kind == "first":
            return _FirstRulePolicy()
        return _NoActionPolicy()


def _first_strategy() -> _TestStrategy:
    return _TestStrategy(policy_kind="first")


def _no_action_strategy() -> _TestStrategy:
    return _TestStrategy(policy_kind="none")


class _TransitionHook(ProverHook):
    def __init__(self) -> None:
        self.choices: list[ActionChoice] = []
        self.transitions: list[Action] = []
        self.proofs_found = 0
        self.strategy_end: tuple[StrategyResult, State | None] | None = None

    def on_choice(self, state: State, choice: ActionChoice) -> None:
        self.choices.append(choice)

    def on_transition(self, state: State, action: Action) -> None:
        self.transitions.append(action)

    def on_proof_found(self, state: State) -> None:
        self.proofs_found += 1

    def on_strategy_end(self, result: StrategyResult, state: State | None) -> None:
        self.strategy_end = (result, state)


def _single_entry_schedule(
    settings: Any,
    *,
    steps: int | None = None,
    timeout_seconds: float | None = None,
) -> StrategySchedule:
    return StrategySchedule.from_weighted(
        [WeightedStrategy(strategy=settings, weight=1)],
        steps=steps,
        timeout_seconds=timeout_seconds,
    )


def test_prover_run_uses_source_file_dirs(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "axioms.ax").write_text("fof(a1,axiom,p).\n", encoding="utf-8")
    problem = tmp_path / "theorem.p"
    problem.write_text("include('axioms.ax').\nfof(c,conjecture,p).\n")

    result = Prover().run(
        problem,
        strategy=_first_strategy(),
        source_file_dirs=(lib_dir,),
    )

    assert result.outcome is ProverOutcome.PROVED
    assert result.szs_status is SZSStatus.THEOREM


def test_prover_run_follows_control_loop_to_theorem(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    run_result = Prover().run(
        str(problem),
        strategy=_first_strategy(),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is ProverOutcome.PROVED
    assert result.szs_status is SZSStatus.THEOREM
    assert result.inference_actions == 2


def test_prover_run_reports_non_theorem_when_no_action(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    run_result = Prover().run(
        str(problem),
        strategy=_no_action_strategy(),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is None
    assert result.inference_actions == 0


def test_prover_run_requires_strategy_or_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    try:
        Prover().run(str(problem))
    except ValueError as err:
        assert "strategy or schedule" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_prover_run_accepts_strategy_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    settings = _first_strategy()
    entry = WeightedStrategy(strategy=settings, weight=3)

    result = Prover().run(str(problem), strategy=entry)

    assert result.outcome is ProverOutcome.PROVED
    assert len(result.strategy_results) == 1
    assert result.strategy_results[0].strategy == settings


def test_prover_run_rejects_schedule_and_strategies(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    settings = _first_strategy()

    try:
        Prover().run(
            str(problem),
            schedule=_single_entry_schedule(settings),
            strategy=settings,
        )
    except ValueError as err:
        assert "either schedule or strategy" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_prover_run_observes_choices_and_transitions_with_hook(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    settings = _first_strategy()
    schedule = StrategySchedule.from_weighted(
        [WeightedStrategy(strategy=settings, weight=1)]
    )
    hook = _TransitionHook()

    result = Prover().run(
        str(problem),
        schedule=schedule,
        hooks=(hook,),
    )

    assert result.outcome is ProverOutcome.PROVED
    assert len(hook.choices) == 2
    assert [choice.chosen_index for choice in hook.choices] == [0, 0]
    assert len(hook.transitions) == 2
    assert hook.proofs_found == 1


def test_prover_hooks_record_strategy_end(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    settings = _first_strategy()
    hook = _TransitionHook()

    result = Prover().run(
        str(problem),
        strategy=settings,
        hooks=(hook,),
    )

    assert result.outcome is ProverOutcome.PROVED
    assert len(hook.transitions) == 2
    assert hook.strategy_end is not None
    assert hook.strategy_end[0].outcome is ProverOutcome.PROVED
    assert hook.strategy_end[1] is not None


def test_prover_transition_hook_records_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    hook = _TransitionHook()

    result = Prover().run(
        str(problem),
        strategy=_first_strategy(),
        hooks=(hook,),
    )

    assert result.outcome is ProverOutcome.PROVED
    assert len(hook.transitions) == 2


def test_prover_caches_matrices_across_schedule_entries(tmp_path, monkeypatch):
    matrix_builds = 0

    def matrix_factory(**kwargs):
        nonlocal matrix_builds
        matrix_builds += 1
        return _non_theorem_matrix()

    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: matrix_factory()
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    schedule = StrategySchedule.from_weighted(
        [
            WeightedStrategy(strategy=PycopStrategy(), weight=1),
            WeightedStrategy(
                strategy=PycopStrategy(
                    dfs=DFSOptions(cut=True, factorization="equal")
                ),
                weight=1,
            ),
        ]
    )
    result = Prover().run(
        str(problem),
        schedule=schedule,
    )

    assert result.outcome is ProverOutcome.ID_FIXED_POINT
    assert matrix_builds == 1


def test_prover_timeout_includes_matrix_construction(tmp_path, monkeypatch):
    def slow_matrix(**kwargs):
        time.sleep(0.02)
        return _non_theorem_matrix()

    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: slow_matrix()
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    settings = _no_action_strategy()

    run_result = Prover().run(
        str(problem),
        schedule=_single_entry_schedule(settings, timeout_seconds=0.001),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is ProverOutcome.TIMEOUT
    assert result.szs_status is SZSStatus.TIMEOUT
    assert result.inference_actions == 0


def test_prover_reports_expired_timeout_before_state_construction(tmp_path):
    problem = tmp_path / "problem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    settings = _no_action_strategy()

    run_result = Prover().run(
        str(problem),
        schedule=_single_entry_schedule(settings, timeout_seconds=0.0),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is ProverOutcome.TIMEOUT
    assert result.szs_status is SZSStatus.TIMEOUT
    assert result.inference_actions == 0


def test_prover_reports_matrix_construction_timeout_as_time_limit(
    tmp_path, monkeypatch
):
    def timeout_matrix(**kwargs):
        _ = kwargs
        raise ProverTimeoutError("Matrix construction timed out")

    monkeypatch.setattr(
        prover_module,
        "matrix_from_file",
        lambda *args, **kwargs: timeout_matrix(**kwargs),
    )
    problem = tmp_path / "problem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    settings = _no_action_strategy()

    run_result = Prover().run(
        str(problem),
        schedule=_single_entry_schedule(settings, timeout_seconds=1.0),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is ProverOutcome.TIMEOUT
    assert result.szs_status is SZSStatus.TIMEOUT
    assert result.inference_actions == 0


def test_pycop_prover_is_direct_base_prover() -> None:
    prover = Prover()

    assert isinstance(prover, Prover)
    assert prover.run.__func__ is Prover.run


def test_pycop_prover_reinitializes_policy_for_each_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    @dataclass(slots=True)
    class TrackingStrategy:
        matrix: MatrixOptions = MatrixOptions()
        policies: list[Policy] = field(default_factory=list)

        def create_policy(self):
            policy = PycopPolicy(PycopStrategy())
            self.policies.append(policy)
            return policy

    settings = TrackingStrategy()
    prover = Prover()

    first = prover.run(str(problem), strategy=settings).strategy_results[0]
    second = prover.run(str(problem), strategy=settings).strategy_results[0]

    assert first.outcome is ProverOutcome.ID_FIXED_POINT
    assert first.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert second.outcome is ProverOutcome.ID_FIXED_POINT
    assert second.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert len(settings.policies) == 2
    assert settings.policies[0] is not settings.policies[1]
