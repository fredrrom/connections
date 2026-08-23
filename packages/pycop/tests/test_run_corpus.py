from __future__ import annotations

from connections.agent import Agent, AgentStatus
from connections.environment.actions import Action
from connections.environment.dynamics import Dynamics
from connections.environment.state import State
from connections.interaction.strategy import (
    MatrixOptions,
    PolicyOptions,
    Strategy,
    StrategySchedule,
)
from pycop.runs import RunRow, run_corpus, run_corpus_records, summarize_run_rows


class _FirstRulePolicy(Agent):
    def __call__(self, state: State) -> Action | None:
        if state.tableau.root.closed:
            self.status = AgentStatus.CLOSED
            return None
        for goal in state.fringe:
            actions = Dynamics.apply_actions(state, goal).ordered()
            if actions:
                return actions[0]
        return None


def _strategy() -> Strategy:
    return Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=_FirstRulePolicy),
    )


def test_run_corpus_records_returns_results_in_input_order(tmp_path):
    first = tmp_path / "a.p"
    second = tmp_path / "b.p"
    first.write_text("fof(c,conjecture,(p => p)).\n", encoding="utf-8")
    second.write_text("fof(c,conjecture,(q => q)).\n", encoding="utf-8")

    records = tuple(
        run_corpus_records(
            (first, second),
            schedule=StrategySchedule.single(_strategy(), steps=10),
            jobs=2,
        )
    )

    assert [record.path.name for record in records] == ["a.p", "b.p"]
    assert [record.row.status for record in records] == ["Theorem", "Theorem"]
    for record in records:
        assert record.result is not None
        assert not hasattr(record.result, "closed_state")


def test_run_corpus_still_yields_rows(tmp_path):
    problem = tmp_path / "tiny.p"
    problem.write_text("fof(c,conjecture,(p => p)).\n", encoding="utf-8")

    rows = tuple(
        run_corpus(
            (problem,),
            schedule=StrategySchedule.single(_strategy(), steps=10),
        )
    )

    assert len(rows) == 1
    assert rows[0].status == "Theorem"


def test_run_corpus_records_can_collect_proof_payloads_in_workers(tmp_path):
    first = tmp_path / "a.p"
    second = tmp_path / "b.p"
    first.write_text("fof(c,conjecture,(p => p)).\n", encoding="utf-8")
    second.write_text("fof(c,conjecture,(q => q)).\n", encoding="utf-8")

    rows = tuple(
        run_corpus_records(
            (first, second),
            schedule=StrategySchedule.single(_strategy(), steps=10),
            jobs=2,
            retain_result=False,
            on_proof_found=_proof_payload,
        )
    )

    assert [record.path.name for record in rows] == ["a.p", "b.p"]
    assert [record.row.status for record in rows] == ["Theorem", "Theorem"]
    assert [record.result for record in rows] == [None, None]
    assert [record.proof_payload for record in rows] == [
        ("a.p", 0, True),
        ("b.p", 0, True),
    ]


def _proof_payload(event):
    return (
        event.problem.path.name,
        event.strategy_index,
        event.state.tableau.root.closed,
    )


def _row(status: str) -> "RunRow":
    return RunRow(
        problem="p",
        path="p.p",
        status=status,
        agent_status=None,
        truncation=None,
        szs_status=status,
        steps=1,
        proof_size=1,
        elapsed_seconds=0.1,
        strategy_count=1,
        winning_strategy_index=None,
    )


def test_summarize_counts_resource_out_and_memory_out():
    rows = (
        _row("Theorem"),
        _row("ResourceOut"),
        _row("ResourceOut"),
        _row("MemoryOut"),
        _row("Timeout"),
    )

    summary = summarize_run_rows(rows)

    assert summary["theorem"] == 1
    assert summary["resource_out"] == 2
    assert summary["memory_out"] == 1
    assert summary["timeout"] == 1
    assert "gave_up" in summary
