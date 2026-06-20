from __future__ import annotations

import time
from typing import Any

import connections.prover.prover as prover_module
from connections.syntax.formula import Atom
from connections.syntax.matrix import Clause, Literal, Matrix
from connections.prover.status import ProverOutcome, SZSStatus
from connections.policy import FirstActionIDPolicy, Policy, PolicyDecision
from connections.prover.actions import Action
from connections.prover.dynamics import Dynamics
from connections.prover.prover import (
    ProblemSpec,
    Prover,
    ProverTimeoutError,
)
from connections.prover.state import State
from connections.prover.strategy import (
    MatrixOptions,
    PolicyOptions,
    Strategy,
    StrategySchedule,
    WeightedStrategy,
)


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
    def __call__(self, state: State) -> PolicyDecision:
        for goal in state.fringe:
            actions = Dynamics.apply_actions(state, goal).ordered()
            if actions:
                return actions[0]
        return None


class _NoActionPolicy(_FirstRulePolicy):
    def __call__(self, state: State) -> PolicyDecision:
        _ = state
        return None


def _first_strategy() -> Strategy:
    return Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=_FirstRulePolicy),
    )


def _no_action_strategy() -> Strategy:
    return Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=_NoActionPolicy),
    )


def _leancop_strategy(**policy_args: Any) -> Strategy:
    return Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=FirstActionIDPolicy, args=policy_args),
    )


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
        ProblemSpec(problem, source_file_dirs=(lib_dir,)),
        schedule=StrategySchedule.single(_first_strategy()),
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
        ProblemSpec(problem),
        schedule=StrategySchedule.single(_first_strategy()),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is ProverOutcome.PROVED
    assert result.szs_status is SZSStatus.THEOREM
    assert result.steps == 2
    assert result.inference_actions == 2


def test_prover_run_accepts_single_strategy(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )

    result = Prover().run(
        ProblemSpec(problem),
        schedule=_first_strategy(),
    )

    assert result.outcome is ProverOutcome.PROVED
    assert len(result.strategy_results) == 1


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
        ProblemSpec(problem),
        schedule=StrategySchedule.single(_no_action_strategy()),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is None
    assert result.steps == 1
    assert result.inference_actions == 0


def test_prover_step_limit_counts_policy_calls(tmp_path, monkeypatch):
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
        ProblemSpec(problem),
        schedule=_single_entry_schedule(_no_action_strategy(), steps=0),
    )
    result = run_result.strategy_results[0]

    assert result.outcome is ProverOutcome.STEP_BUDGET
    assert result.steps == 0
    assert result.inference_actions == 0


def test_prover_run_requires_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    run = Prover().run
    try:
        run(ProblemSpec(problem))  # ty: ignore[missing-argument]
    except TypeError as err:
        assert "schedule" in str(err)
    else:
        raise AssertionError("expected TypeError")


def test_prover_run_accepts_scheduled_entries(tmp_path, monkeypatch):
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

    result = Prover().run(
        ProblemSpec(problem),
        schedule=StrategySchedule.from_weighted((entry,)),
    )

    assert result.outcome is ProverOutcome.PROVED
    assert len(result.strategy_results) == 1
    assert result.strategy_results[0].strategy == settings


def test_prover_run_passes_closed_state_to_proof_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        prover_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    schedule = StrategySchedule.from_weighted(
        [WeightedStrategy(strategy=_first_strategy(), weight=1)]
    )

    result = Prover().run(
        ProblemSpec(problem),
        schedule=schedule,
        on_proof_found=lambda event: event.state.tableau.root.closed,
    )

    assert result.outcome is ProverOutcome.PROVED
    assert result.proof_payload is True
    assert not hasattr(result, "closed_state")
    assert not hasattr(result.strategy_results[0], "closed_state")


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
            WeightedStrategy(strategy=_leancop_strategy(), weight=1),
            WeightedStrategy(
                strategy=_leancop_strategy(cut=True, factorization="equal"),
                weight=1,
            ),
        ]
    )
    result = Prover().run(
        ProblemSpec(problem),
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
        ProblemSpec(problem),
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
        ProblemSpec(problem),
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
        ProblemSpec(problem),
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
    class TrackingPolicy(FirstActionIDPolicy):
        policies: list[Policy] = []

        def __init__(self) -> None:
            super().__init__()
            self.policies.append(self)

    TrackingPolicy.policies = []
    settings = Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=TrackingPolicy),
    )
    prover = Prover()

    first = prover.run(
        ProblemSpec(problem),
        schedule=StrategySchedule.single(settings),
    ).strategy_results[0]
    second = prover.run(
        ProblemSpec(problem),
        schedule=StrategySchedule.single(settings),
    ).strategy_results[0]

    assert first.outcome is ProverOutcome.ID_FIXED_POINT
    assert first.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert second.outcome is ProverOutcome.ID_FIXED_POINT
    assert second.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert len(TrackingPolicy.policies) == 2
    assert TrackingPolicy.policies[0] is not TrackingPolicy.policies[1]
