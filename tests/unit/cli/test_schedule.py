from __future__ import annotations

import pytest

from connections.pycop.schedule import SCHEDULE_BY_LOGIC, load_schedule_entries
from connections.pycop.settings_codec import LeancopSettingsCodec
from connections.pycop.strategy import PycopStrategy
from connections.prover.strategy import StrategySchedule, WeightedStrategy


def test_pycop_schedule_has_expected_classical_first_strategy():
    tokens = [
        LeancopSettingsCodec.to_tokens(entry.strategy)
        for entry in SCHEDULE_BY_LOGIC["classical"]
    ]
    assert tokens[0] == ["cut", "comp(7)"]
    assert tokens[1] == ["def", "conj", "cut"]
    assert tokens[-1] == ["def"]

    schedule = StrategySchedule.from_weighted(SCHEDULE_BY_LOGIC["classical"]).entries
    assert len(schedule) == 30
    assert schedule[0].strategy.dfs.cut is True
    assert schedule[0].strategy.id.comp == 7
    assert schedule[-1].strategy.matrix.translation == "def"


def test_load_schedule_entries_from_json_file(tmp_path):
    path = tmp_path / "schedule.json"
    path.write_text(
        """
        {
          "entries": [
            {"settings": ["cut", "comp(7)"], "weight": 3},
            {"tokens": ["def", "conj"], "weight": 1}
          ]
        }
        """,
        encoding="utf-8",
    )

    entries = load_schedule_entries(path)

    assert len(entries) == 2
    assert entries[0].weight == 3
    assert entries[0].strategy.dfs.cut is True
    assert entries[0].strategy.id.comp == 7
    assert entries[1].strategy.matrix.translation == "def"
    assert entries[1].strategy.matrix.start_clauses == "conjecture"


def test_load_schedule_entries_from_builtin_name():
    entries = load_schedule_entries("classical")

    assert entries == SCHEDULE_BY_LOGIC["classical"]


def test_pycop_schedule_has_expected_intuitionistic_first_strategy():
    schedule = StrategySchedule.from_weighted(SCHEDULE_BY_LOGIC["intuitionistic"]).entries
    assert len(schedule) == 5
    assert schedule[0].strategy.matrix.translation == "def"
    assert schedule[0].strategy.dfs.scut is True
    assert schedule[0].strategy.id.comp == 7


def test_pycop_schedule_has_expected_modal_shape():
    tokens = [
        LeancopSettingsCodec.to_tokens(entry.strategy)
        for entry in SCHEDULE_BY_LOGIC["S4"]
    ]
    assert tokens[0] == ["cut", "scut", "comp(7)"]
    assert tokens[-1] == ["def"]

    schedule = StrategySchedule.from_weighted(SCHEDULE_BY_LOGIC["S4"]).entries
    assert len(schedule) == 10
    assert schedule[0].strategy.dfs.cut is True
    assert schedule[0].strategy.dfs.scut is True
    assert schedule[0].strategy.id.comp == 7
    assert any(entry.strategy.matrix.reorder > 0 for entry in schedule)


def test_schedule_step_budget_allocation_sums_to_total():
    schedule = StrategySchedule.from_weighted(SCHEDULE_BY_LOGIC["classical"], steps=1000)
    budget = [entry.step_limit for entry in schedule.entries]
    assert len(budget) == len(SCHEDULE_BY_LOGIC["classical"])
    assert all(value is not None for value in budget)
    assert sum(value for value in budget if value is not None) == 1000


def test_schedule_time_budget_allocation_sums_to_total():
    schedule = StrategySchedule.from_weighted(SCHEDULE_BY_LOGIC["S4"], timeout_seconds=120.0)
    budget = [entry.timeout_seconds for entry in schedule.entries]
    assert len(budget) == len(SCHEDULE_BY_LOGIC["S4"])
    assert all(value is not None for value in budget)
    assert sum(value for value in budget if value is not None) == pytest.approx(120.0)


def test_schedule_rejects_zero_total_weight_for_budget_allocation():
    with pytest.raises(ValueError, match="weights must sum to a positive value"):
        StrategySchedule.from_weighted(
            [WeightedStrategy(strategy=PycopStrategy(), weight=0)],
            steps=1,
        )

    with pytest.raises(ValueError, match="weights must sum to a positive value"):
        StrategySchedule.from_weighted(
            [WeightedStrategy(strategy=PycopStrategy(), weight=0)],
            timeout_seconds=1.0,
        )
