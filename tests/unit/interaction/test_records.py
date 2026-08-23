"""The serialization contract, and that trajectories carry replay identity."""

from __future__ import annotations

import json

from connections.interaction import Problem, build_state, run_schedule
from connections.interaction.records import RESULT_SCHEMA, resolve_record
from connections.interaction.strategy import MatrixOptions, StrategySchedule

from tests.unit.interaction.test_run import _leancop_strategy, _theorem_matrix


def test_result_dict_is_versioned_and_json_serializable(tmp_path, monkeypatch):
    import connections.interaction.run as run_module

    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text("fof(c,conjecture,p|~p).\n", encoding="utf-8")

    result = run_schedule(
        Problem(problem),
        schedule=StrategySchedule.single(_leancop_strategy()),
        record_trajectory=True,
    )
    payload = result.to_dict()

    assert payload["schema"] == RESULT_SCHEMA
    json.dumps(payload)  # the whole contract must be JSON-clean
    trajectory = payload["strategy_results"][0]["trajectory"]
    assert trajectory, "recorded trajectories serialize"
    assert all("kind" in record for record in trajectory)


def test_serialized_trajectory_replays_to_a_closed_state(tmp_path, monkeypatch):
    """Replay identity: records plus a fresh initial state rebuild the proof."""
    import connections.interaction.run as run_module

    monkeypatch.setattr(
        run_module, "matrix_from_file", lambda *args, **kwargs: _theorem_matrix()
    )
    problem = tmp_path / "theorem.p"
    problem.write_text("fof(c,conjecture,p|~p).\n", encoding="utf-8")

    result = run_schedule(
        Problem(problem),
        schedule=StrategySchedule.single(_leancop_strategy()),
        record_trajectory=True,
    )
    records = result.to_dict()["strategy_results"][0]["trajectory"]
    assert result.szs_status is not None and records

    from connections.environment.dynamics import Dynamics

    state = build_state(Problem(problem), matrix_options=MatrixOptions())
    for record in records:
        action = resolve_record(state, record)
        assert action is not None, f"unresolvable record: {record}"
        Dynamics.transition(state, action)

    assert state.tableau.root.closed, "the replayed derivation closes"
