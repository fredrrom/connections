"""Corpus selection, records, and sharded runs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from executor.plan import run_plan

from corpus import Attempt, corpus_run, read_attempts, select_problems, shard, summarize


def _corpus(tmp_path: Path, names: list[str]) -> Path:
    root = tmp_path / "problems"
    root.mkdir()
    for name in names:
        (root / name).write_text("cnf(a,axiom,(p)).", encoding="utf-8")
    return root


def _ok(problem: Path, steps: int = 7) -> Attempt:
    return Attempt(
        problem=problem.name,
        status="Theorem",
        outcome="Proved",
        steps=steps,
        elapsed_seconds=0.5,
    )


# ----------------------------------------------------------------- selection


def test_problems_are_ordered_the_same_everywhere(tmp_path: Path):
    # Filesystem order varies by platform; a resumed run must see the same list.
    root = _corpus(tmp_path, ["c.p", "a.p", "b.p"])

    assert [p.name for p in select_problems([root])] == ["a.p", "b.p", "c.p"]


def test_a_directory_is_searched_recursively(tmp_path: Path):
    root = _corpus(tmp_path, ["a.p"])
    (root / "sub").mkdir()
    (root / "sub" / "b.p").write_text("cnf(a,axiom,(p)).", encoding="utf-8")

    assert len(select_problems([root])) == 2


def test_duplicate_sources_yield_one_problem_each(tmp_path: Path):
    root = _corpus(tmp_path, ["a.p"])

    assert len(select_problems([root, root, root / "a.p"])) == 1


def test_shuffling_is_reproducible_and_limit_samples_it(tmp_path: Path):
    root = _corpus(tmp_path, [f"{i:02d}.p" for i in range(20)])

    first = select_problems([root], shuffle_seed=7)
    again = select_problems([root], shuffle_seed=7)
    other = select_problems([root], shuffle_seed=8)

    assert first == again
    assert first != other
    # A limit applies after shuffling, so a truncated run is a sample rather
    # than the alphabetical head.
    assert select_problems([root], shuffle_seed=7, limit=5) == first[:5]


def test_sharding_is_deterministic_and_covers_everything(tmp_path: Path):
    problems = select_problems([_corpus(tmp_path, [f"{i:02d}.p" for i in range(10)])])

    shards = shard(problems, size=3)

    assert [len(s) for s in shards] == [3, 3, 3, 1]
    assert tuple(p for s in shards for p in s.problems) == problems
    assert shard(problems, size=3) == shards


# ------------------------------------------------------------------- records


def test_an_attempt_round_trips(tmp_path: Path):
    attempt = Attempt(
        problem="a.p",
        status="Theorem",
        outcome="Proved",
        steps=12,
        elapsed_seconds=1.5,
        policy="dfs@3",
        payload={"proof_path": [1, 2, 3]},
    )

    assert Attempt.from_json(attempt.to_json()) == attempt


def test_only_proof_producing_statuses_count_as_solved():
    def with_status(status):
        return Attempt(problem="a.p", status=status, outcome=None, steps=0, elapsed_seconds=0.0)

    assert with_status("Theorem").solved
    assert with_status("Unsatisfiable").solved
    # Exhausting the search space answers the problem but proves nothing.
    assert not with_status("CounterSatisfiable").solved
    assert not with_status("Satisfiable").solved
    assert not with_status(None).solved


def test_mean_steps_ignores_unsolved_attempts():
    attempts = [
        Attempt(problem="a", status="Theorem", outcome=None, steps=10, elapsed_seconds=1.0),
        Attempt(problem="b", status="Theorem", outcome=None, steps=20, elapsed_seconds=1.0),
        # An unsolved run stops at the budget; averaging it in would measure
        # the budget rather than the search.
        Attempt(problem="c", status=None, outcome="StepBudget", steps=1000, elapsed_seconds=9.0),
    ]

    summary = summarize(attempts)

    assert summary.solved == 2
    assert summary.mean_steps == 15.0
    assert summary.attempted == 3


def test_a_torn_final_line_is_tolerated(tmp_path: Path):
    path = tmp_path / "shard.jsonl"
    good = Attempt(problem="a.p", status="Theorem", outcome=None, steps=1, elapsed_seconds=0.1)
    path.write_text(f"{good.to_json()}\n{{\"problem\": \"b.p\", \"st", encoding="utf-8")

    assert [a.problem for a in read_attempts(path)] == ["a.p"]


# ----------------------------------------------------------------- corpus run


def test_a_corpus_run_attempts_every_problem(tmp_path: Path):
    problems = select_problems([_corpus(tmp_path, [f"{i:02d}.p" for i in range(7)])])
    run = corpus_run(tmp_path / "run", problems, shard_size=3)

    run_plan(lambda: run.tasks(_ok), worker_id="w0")

    assert len(run.attempts()) == 7
    assert run.summary_path.exists()


def test_the_summary_waits_for_every_shard(tmp_path: Path):
    problems = select_problems([_corpus(tmp_path, [f"{i:02d}.p" for i in range(6)])])
    run = corpus_run(tmp_path / "run", problems, shard_size=2)

    order: list[str] = []

    def prover(problem: Path) -> Attempt:
        order.append(problem.name)
        return _ok(problem)

    run_plan(lambda: run.tasks(prover), worker_id="w0")

    summary = run.summary_path.read_text(encoding="utf-8")
    assert '"attempted": 6' in summary
    assert '"solved": 6' in summary


def test_a_finished_run_resumes_without_work(tmp_path: Path):
    problems = select_problems([_corpus(tmp_path, [f"{i:02d}.p" for i in range(5)])])
    run = corpus_run(tmp_path / "run", problems, shard_size=2)
    run_plan(lambda: run.tasks(_ok), worker_id="w0")

    def must_not_run(problem: Path) -> Attempt:
        raise AssertionError("already published")

    stats = run_plan(lambda: run.tasks(must_not_run), worker_id="w1")

    assert stats.completed == 0


def test_a_failing_problem_does_not_lose_its_shard(tmp_path: Path):
    problems = select_problems([_corpus(tmp_path, ["a.p", "b.p", "c.p"])])
    run = corpus_run(tmp_path / "run", problems, shard_size=3)

    def flaky(problem: Path) -> Attempt:
        if problem.name == "b.p":
            raise RuntimeError("parser blew up")
        return _ok(problem)

    run_plan(lambda: run.tasks(flaky), worker_id="w0")

    attempts = {a.problem: a for a in run.attempts()}
    assert len(attempts) == 3
    assert attempts["b.p"].error is not None
    assert attempts["b.p"].outcome == "Error"
    assert attempts["a.p"].solved and attempts["c.p"].solved


def test_a_fleet_splits_the_corpus_without_repeating_work(tmp_path: Path):
    problems = select_problems([_corpus(tmp_path, [f"{i:03d}.p" for i in range(60)])])
    run = corpus_run(tmp_path / "run", problems, shard_size=5)
    seen: list[str] = []

    def prover(problem: Path) -> Attempt:
        seen.append(problem.name)
        return _ok(problem)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i: run_plan(lambda: run.tasks(prover), worker_id=f"w{i}"), range(6)))

    assert sorted(seen) == sorted(p.name for p in problems)
    assert len(run.attempts()) == 60
