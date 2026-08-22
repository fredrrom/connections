from __future__ import annotations

from typing import Any

import connections.interaction.run as run_module
from connections.syntax.formula import Atom
from connections.syntax.matrix import Clause, Literal, Matrix
from connections.interaction.szs import SZSStatus
from connections.interaction.truncation import Truncation
from connections.agent import (
    Agent,
    AgentOptions,
    AgentStatus,
    OnlineIDAgent,
)
from connections.env.actions import Action
from connections.env.dynamics import Dynamics
from connections.interaction.run import Problem, run_schedule as run_problem
from connections.env.state import State
from connections.interaction.strategy import (
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


class _FirstRulePolicy(Agent):
    def __call__(self, state: State) -> Action | None:
        if state.tableau.root.closed:
            self.status = AgentStatus.CLOSED
            return None
        for goal in state.fringe:
            actions = Dynamics.apply_actions(
                state,
                goal,
            ).ordered()
            if actions:
                return actions[0]
        return None


class _NoActionPolicy(_FirstRulePolicy):
    def __call__(self, state: State) -> Action | None:
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


def _id_agent(**options):
    return OnlineIDAgent(lambda s, a: a[0], AgentOptions(**options))


def _leancop_strategy(**policy_args: Any) -> Strategy:
    return Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=_id_agent, args=policy_args),
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

    result = run_problem(
        Problem(problem, source_file_dirs=(lib_dir,)),
        schedule=StrategySchedule.single(_first_strategy()),
    )

    assert result.szs_status is SZSStatus.THEOREM
    assert result.szs_status is SZSStatus.THEOREM


def test_prover_run_follows_control_loop_to_theorem(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    run_result = run_problem(
        Problem(problem),
        schedule=StrategySchedule.single(_first_strategy()),
    )
    result = run_result.strategy_results[0]

    assert result.szs_status is SZSStatus.THEOREM
    assert result.szs_status is SZSStatus.THEOREM
    assert result.steps == 2
    assert result.proof_size == 2


def test_prover_run_accepts_single_strategy(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )

    result = run_problem(
        Problem(problem),
        schedule=_first_strategy(),
    )

    assert result.szs_status is SZSStatus.THEOREM
    assert len(result.strategy_results) == 1


def test_prover_run_reports_non_theorem_when_no_action(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    run_result = run_problem(
        Problem(problem),
        schedule=StrategySchedule.single(_no_action_strategy()),
    )
    result = run_result.strategy_results[0]

    # An agent that offers nothing and makes no claim is giving up: the
    # honest default, never a countermodel.
    assert result.szs_status is SZSStatus.GAVE_UP
    assert result.szs_status is SZSStatus.GAVE_UP
    # A step is an application of T, so an agent call that yields no action is
    # not a step. The agent was consulted once and offered nothing.
    assert result.steps == 0
    assert result.proof_size == 0


def test_prover_step_limit_counts_transitions(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    run_result = run_problem(
        Problem(problem),
        schedule=_single_entry_schedule(_no_action_strategy(), steps=0),
    )
    result = run_result.strategy_results[0]

    assert result.truncation is Truncation.STEPS
    assert result.steps == 0
    assert result.proof_size == 0


def test_prover_run_requires_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    run = run_problem
    try:
        run(Problem(problem))  # ty: ignore[missing-argument]
    except TypeError as err:
        assert "schedule" in str(err)
    else:
        raise AssertionError("expected TypeError")


def test_prover_run_accepts_scheduled_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    settings = _first_strategy()
    entry = WeightedStrategy(strategy=settings, weight=3)

    result = run_problem(
        Problem(problem),
        schedule=StrategySchedule.from_weighted((entry,)),
    )

    assert result.szs_status is SZSStatus.THEOREM
    assert len(result.strategy_results) == 1
    assert result.strategy_results[0].strategy == settings


def test_prover_run_passes_closed_state_to_proof_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    schedule = StrategySchedule.from_weighted(
        [WeightedStrategy(strategy=_first_strategy(), weight=1)]
    )

    result = run_problem(
        Problem(problem),
        schedule=schedule,
        on_proof_found=lambda event: event.state.tableau.root.closed,
    )

    assert result.szs_status is SZSStatus.THEOREM
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
        run_module, "matrix_from_file", lambda *args, **kwargs: matrix_factory()
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
    result = run_problem(
        Problem(problem),
        schedule=schedule,
    )

    # The first entry is complete and exhausts; the second runs cut and can
    # only give up. The schedule keeps the stronger verdict.
    assert result.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert result.strategy_results[0].agent_status is AgentStatus.ID_FIXED_POINT
    assert result.strategy_results[1].agent_status is AgentStatus.GAVE_UP
    assert matrix_builds == 1


def test_pycop_prover_reinitializes_policy_for_each_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    created: list[Agent] = []

    def tracking_agent(**options):
        agent = OnlineIDAgent(lambda s, a: a[0], AgentOptions(**options))
        created.append(agent)
        return agent

    settings = Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=tracking_agent),
    )

    first_result = run_problem(
        Problem(problem),
        schedule=StrategySchedule.single(settings),
    ).strategy_results[0]
    second_result = run_problem(
        Problem(problem),
        schedule=StrategySchedule.single(settings),
    ).strategy_results[0]

    assert first_result.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert first_result.agent_status is AgentStatus.ID_FIXED_POINT
    assert first_result.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert second_result.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert second_result.agent_status is AgentStatus.ID_FIXED_POINT
    assert second_result.szs_status is SZSStatus.COUNTER_SATISFIABLE
    assert len(created) == 2
    assert created[0] is not created[1]


def test_the_package_exports_the_function_not_a_module():
    """The exported names must be callables, not modules.

    A submodule sharing a function's name shadows it: Python binds a submodule
    as an attribute of its package, and that lookup wins before any lazy
    export in __init__. This test is what notices.
    """
    import types

    from connections.interaction import build_state, rollout, run_schedule

    for name, obj in (
        ("run_schedule", run_schedule),
        ("build_state", build_state),
        ("rollout", rollout),
    ):
        assert callable(obj), f"connections.interaction.{name} is {obj!r}"
        assert not isinstance(obj, types.ModuleType), f"{name} resolved to a module"


def test_importing_a_submodule_does_not_shadow_the_function():
    """Importing connections.interaction.rollout must not rebind the package attribute."""
    import types

    import connections.interaction
    import connections.interaction.rollout  # noqa: F401  -- the adversarial case

    assert callable(connections.interaction.rollout)
    assert not isinstance(connections.interaction.rollout, types.ModuleType)
    assert callable(connections.interaction.run_schedule)


def test_a_persistent_agent_is_reused_across_schedule_entries(tmp_path, monkeypatch):
    """Agent lifetime is the caller's choice: passing an agent reuses it."""
    monkeypatch.setattr(
        run_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text("fof(a1,axiom,p).\nfof(c,conjecture,q).\n", encoding="utf-8")

    calls = []

    class _Persistent(Agent):
        def __call__(self, state):
            calls.append(self)
            return None

    persistent = _Persistent()
    schedule = StrategySchedule.from_weighted(
        [
            WeightedStrategy(strategy=_leancop_strategy(), weight=1),
            WeightedStrategy(strategy=_leancop_strategy(cut=True), weight=1),
        ]
    )
    run_problem(Problem(problem), schedule=schedule, agent=persistent)

    assert len(calls) == 2
    assert all(agent is persistent for agent in calls)


def test_record_trajectory_attaches_actions_to_the_result(tmp_path, monkeypatch):
    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text("fof(c,conjecture,p|~p).\n", encoding="utf-8")

    recorded = run_problem(
        Problem(problem),
        schedule=StrategySchedule.single(_leancop_strategy()),
        record_trajectory=True,
    ).strategy_results[0]
    unrecorded = run_problem(
        Problem(problem),
        schedule=StrategySchedule.single(_leancop_strategy()),
    ).strategy_results[0]

    assert recorded.trajectory is not None
    assert len(recorded.trajectory) == recorded.steps
    assert unrecorded.trajectory is None
    assert unrecorded.steps == recorded.steps


def test_expired_strategy_deadline_is_best_effort_time_budget(tmp_path, monkeypatch):
    """connections imposes no alarm: an expired deadline is noticed between
    steps, reported as the strategy's own budget running out."""
    monkeypatch.setattr(
        run_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text("fof(a1,axiom,p).\nfof(c,conjecture,q).\n", encoding="utf-8")

    result = run_problem(
        Problem(problem),
        schedule=_single_entry_schedule(_leancop_strategy(), timeout_seconds=0.0),
    ).strategy_results[0]

    assert result.truncation is Truncation.TIME
    assert result.szs_status is SZSStatus.RESOURCE_OUT
    assert result.steps == 0


def test_cached_agent_reused_across_entries_with_isolated_episodes(
    tmp_path, monkeypatch
):
    """One agent per recipe within the run; each entry is a fresh episode.

    The schedule lists the same strategy object twice, so the agent cache
    serves one instance to both entries. Episode detection from the percept
    must make the second entry behave exactly like a fresh agent would.
    """
    monkeypatch.setattr(
        run_module,
        "matrix_from_file",
        lambda *args, **kwargs: _non_theorem_matrix(),
    )
    problem = tmp_path / "non_theorem.p"
    problem.write_text("fof(a1,axiom,p).\nfof(c,conjecture,q).\n", encoding="utf-8")

    created = []
    real_instantiate = PolicyOptions.instantiate

    def counting(self):
        agent = real_instantiate(self)
        created.append(agent)
        return agent

    monkeypatch.setattr(PolicyOptions, "instantiate", counting)

    shared = _leancop_strategy()
    schedule = StrategySchedule.from_weighted(
        [
            WeightedStrategy(strategy=shared, weight=1),
            WeightedStrategy(strategy=shared, weight=1),
        ]
    )
    result = run_problem(Problem(problem), schedule=schedule)

    assert len(created) == 1, "one agent per recipe within the run"
    first_entry, second_entry = result.strategy_results
    assert first_entry.szs_status == second_entry.szs_status
    assert first_entry.agent_status == second_entry.agent_status
    assert first_entry.steps == second_entry.steps, (
        "the second episode must look exactly like the first: derivation-bound "
        "memory died at the boundary, and the comp switch was undone"
    )
