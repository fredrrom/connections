"""Tests for the coordination primitives.

The properties worth testing are the ones that only show up under concurrency
and failure: two workers must not both do a task, a killed worker must not
leave a half-written artifact or a permanent lock, and a task that raises must
stay available for someone else.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from executor import (
    attempt_count,
    commit_dir,
    commit_file,
    drain,
    heartbeat,
    is_done,
    new_tmp,
    record_attempt,
    release,
    try_claim,
)
from executor import claim as claim_mod


class FakeTask:
    """Minimal structural Task: a key and the artifact it publishes."""

    def __init__(self, target: Path, key: str = "work") -> None:
        self._target = target
        self._key = key

    @property
    def key(self) -> str:
        return self._key

    @property
    def target(self) -> Path:
        return self._target


# ---------------------------------------------------------------- artifacts


def test_commit_file_publishes_atomically(tmp_path: Path):
    final = tmp_path / "out" / "summary.json"
    tmp = new_tmp(final)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text("{}", encoding="utf-8")

    assert commit_file(tmp, final)
    assert final.read_text(encoding="utf-8") == "{}"
    assert not tmp.exists()


def test_new_tmp_stays_in_the_target_directory(tmp_path: Path):
    # A rename is only atomic within a filesystem; a tmp elsewhere would copy.
    final = tmp_path / "out" / "model.pt"
    assert new_tmp(final).parent == final.parent


def test_losing_the_commit_race_discards_our_work(tmp_path: Path):
    final = tmp_path / "out" / "dataset"
    final.mkdir(parents=True)
    (final / "winner").write_text("first", encoding="utf-8")

    tmp = new_tmp(final)
    tmp.mkdir()
    (tmp / "loser").write_text("second", encoding="utf-8")

    assert not commit_dir(tmp, final)
    assert (final / "winner").exists()      # the published result stands
    assert not (final / "loser").exists()
    assert not tmp.exists()                 # and ours is cleaned up


# -------------------------------------------------------------------- claims


def test_only_one_of_many_workers_claims_a_task(tmp_path: Path):
    target = tmp_path / "cell" / "summary.json"
    target.parent.mkdir(parents=True)

    with ThreadPoolExecutor(max_workers=16) as pool:
        winners = list(pool.map(lambda i: try_claim(target, "summary", f"w{i}"), range(16)))

    assert sum(winners) == 1


def test_a_stale_claim_is_reclaimed(tmp_path: Path, monkeypatch):
    target = tmp_path / "cell" / "summary.json"
    target.parent.mkdir(parents=True)
    assert try_claim(target, "summary", "dead-worker")
    assert not try_claim(target, "summary", "other")     # still owned

    # Age the claim past the staleness window.
    owner = target.parent / ".claim_summary" / "owner.json"
    old = time.time() - claim_mod.CLAIM_STALE_SECONDS - 1
    os.utime(owner, (old, old))

    assert try_claim(target, "summary", "other")


def test_a_claim_directory_without_an_owner_is_stale(tmp_path: Path):
    # Only reachable by crashing between mkdir and the owner write.
    target = tmp_path / "cell" / "summary.json"
    (target.parent / ".claim_summary").mkdir(parents=True)

    assert try_claim(target, "summary", "worker")


def test_heartbeat_reports_a_lost_claim(tmp_path: Path):
    target = tmp_path / "cell" / "summary.json"
    target.parent.mkdir(parents=True)
    try_claim(target, "summary", "worker")
    assert heartbeat(target, "summary")

    release(target, "summary")
    assert not heartbeat(target, "summary")


def test_sibling_tasks_do_not_share_a_claim(tmp_path: Path):
    # Two tasks publishing into one directory must be independently claimable.
    d = tmp_path / "cell"
    d.mkdir()
    assert try_claim(d / "summary.json", "summary", "a")
    assert try_claim(d / "model", "model", "b")


def test_attempts_accumulate(tmp_path: Path):
    target = tmp_path / "cell" / "summary.json"
    target.parent.mkdir(parents=True)

    record_attempt(target, "summary", "boom")
    record_attempt(target, "summary", "boom again")

    assert attempt_count(target, "summary") == 2
    assert attempt_count(target, "summary", within_seconds=3600) == 2


# --------------------------------------------------------------------- drain


def test_drain_runs_ready_work_and_stops_when_empty(tmp_path: Path):
    targets = [tmp_path / f"t{i}.json" for i in range(5)]

    def ready():
        return [FakeTask(t) for t in targets if not t.exists()]

    def run(task):
        tmp = new_tmp(task.target)
        tmp.write_text("done", encoding="utf-8")
        commit_file(tmp, task.target)

    stats = drain(ready, run, worker_id="w0")

    assert stats.completed == 5
    assert all(t.exists() for t in targets)


def test_drain_skips_already_published_work(tmp_path: Path):
    done = tmp_path / "done.json"
    done.write_text("earlier", encoding="utf-8")

    def ready():
        return [FakeTask(done)]

    stats = drain(ready, lambda task: pytest.fail("should not run"), worker_id="w0")

    assert stats.claimed == 0
    assert done.read_text(encoding="utf-8") == "earlier"


def test_a_failing_task_is_recorded_and_left_for_a_retry(tmp_path: Path):
    target = tmp_path / "t.json"
    calls = {"n": 0}

    def ready():
        return [] if target.exists() else [FakeTask(target)]

    def run(task):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        tmp = new_tmp(task.target)
        tmp.write_text("ok", encoding="utf-8")
        commit_file(tmp, task.target)

    first = drain(ready, run, worker_id="w0")
    assert first.failed == 1
    assert not target.exists()
    assert attempt_count(target, "work") == 1
    # The claim must not survive the failure, or the task is stuck forever.
    assert try_claim(target, "work", "someone-else")
    release(target, "work")

    second = drain(ready, run, worker_id="w1")
    assert second.completed == 1
    assert target.exists()


def test_concurrent_drainers_do_each_task_once(tmp_path: Path):
    targets = [tmp_path / f"t{i}.json" for i in range(24)]
    runs: list[Path] = []

    def ready():
        return [FakeTask(t) for t in targets if not t.exists()]

    def run(task):
        runs.append(task.target)
        time.sleep(0.005)          # widen the window for a double-claim
        tmp = new_tmp(task.target)
        tmp.write_text("done", encoding="utf-8")
        commit_file(tmp, task.target)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: drain(ready, run, worker_id=f"w{i}"), range(8)))

    assert all(t.exists() for t in targets)
    assert sorted(runs) == sorted(targets)      # nothing done twice


def test_drain_honours_stop(tmp_path: Path):
    targets = [tmp_path / f"t{i}.json" for i in range(10)]
    seen = {"n": 0}

    def ready():
        return [FakeTask(t) for t in targets if not t.exists()]

    def run(task):
        seen["n"] += 1
        tmp = new_tmp(task.target)
        tmp.write_text("done", encoding="utf-8")
        commit_file(tmp, task.target)

    drain(ready, run, worker_id="w0", stop=lambda: seen["n"] >= 3)

    assert seen["n"] == 3
    assert sum(t.exists() for t in targets) == 3
