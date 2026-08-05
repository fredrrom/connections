"""Declared plans: does work actually run after its dependencies?

These use a proof-aggregation-shaped plan -- shards, then a dataset over them,
then a model, then the next iteration's shards -- because that is the ordering
the real experiments need, and it is the thing worth proving.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from imitation import commit_file, new_tmp
from imitation.plan import TaskSpec, ready_tasks, run_plan


def _publish(target: Path, order: list[str], label: str) -> None:
    order.append(label)
    tmp = new_tmp(target)
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(label, encoding="utf-8")
    commit_file(tmp, target)


def _aggregation_plan(root: Path, order: list[str], iterations: int = 2, shards: int = 3):
    """shards -> dataset -> model -> next iteration's shards."""

    def tasks():
        out: list[TaskSpec] = []
        for k in range(iterations):
            model_prev = root / f"iter_{k - 1}" / "model.pt"
            shard_paths = tuple(root / f"iter_{k}" / f"shard_{i}.jsonl" for i in range(shards))
            for i, shard in enumerate(shard_paths):
                out.append(
                    TaskSpec(
                        key=f"shard_{i}",
                        target=shard,
                        # iteration 0 rolls out with the base policy; later
                        # iterations need the model trained on k-1.
                        needs=() if k == 0 else (model_prev,),
                        run=lambda t=shard, l=f"shard{k}.{i}": _publish(t, order, l),
                    )
                )
            dataset = root / f"iter_{k}" / "dataset.jsonl"
            out.append(
                TaskSpec(
                    key="dataset",
                    target=dataset,
                    needs=shard_paths,
                    run=lambda t=dataset, l=f"dataset{k}": _publish(t, order, l),
                )
            )
            model = root / f"iter_{k}" / "model.pt"
            out.append(
                TaskSpec(
                    key="model",
                    target=model,
                    needs=(dataset,),
                    run=lambda t=model, l=f"model{k}": _publish(t, order, l),
                )
            )
        return out

    return tasks


def test_a_task_waits_for_its_inputs(tmp_path: Path):
    order: list[str] = []
    run_plan(_aggregation_plan(tmp_path, order), worker_id="w0")

    # Every shard of an iteration precedes its dataset, which precedes its
    # model, which precedes the next iteration's shards.
    assert order.index("dataset0") > max(order.index(f"shard0.{i}") for i in range(3))
    assert order.index("model0") > order.index("dataset0")
    assert min(order.index(f"shard1.{i}") for i in range(3)) > order.index("model0")
    assert order.index("dataset1") > max(order.index(f"shard1.{i}") for i in range(3))


def test_everything_gets_published(tmp_path: Path):
    order: list[str] = []
    stats = run_plan(_aggregation_plan(tmp_path, order), worker_id="w0")

    assert stats.completed == 2 * (3 + 1 + 1)
    assert (tmp_path / "iter_1" / "model.pt").exists()


def test_independent_tasks_are_ready_together(tmp_path: Path):
    # Shards of one iteration have no dependency on each other, so a plan must
    # expose them all at once -- otherwise a fleet serialises on a false order.
    order: list[str] = []
    tasks = _aggregation_plan(tmp_path, order)

    ready = ready_tasks(tasks())

    assert sorted(t.key for t in ready) == ["shard_0", "shard_1", "shard_2"]


def test_resume_skips_published_work(tmp_path: Path):
    order: list[str] = []
    tasks = _aggregation_plan(tmp_path, order)
    run_plan(tasks, worker_id="w0")

    resumed: list[str] = []
    again = run_plan(_aggregation_plan(tmp_path, resumed), worker_id="w1")

    assert again.completed == 0
    assert resumed == []


def test_a_partial_tree_resumes_from_where_it_stopped(tmp_path: Path):
    order: list[str] = []
    # Publish iteration 0's shards by hand, as a killed run would have left them.
    for i in range(3):
        _publish(tmp_path / "iter_0" / f"shard_{i}.jsonl", order, f"pre{i}")
    order.clear()

    run_plan(_aggregation_plan(tmp_path, order), worker_id="w0")

    assert not [label for label in order if label.startswith("shard0.")]
    assert order[0] == "dataset0"


def test_a_fleet_agrees_on_the_same_plan(tmp_path: Path):
    order: list[str] = []
    tasks = _aggregation_plan(tmp_path, order, iterations=2, shards=6)

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i: run_plan(tasks, worker_id=f"w{i}"), range(6)))

    assert len(order) == 2 * (6 + 1 + 1)          # nothing done twice
    assert (tmp_path / "iter_1" / "model.pt").exists()


def test_a_task_blocked_forever_does_not_hang(tmp_path: Path):
    missing = tmp_path / "never" / "arrives.json"
    target = tmp_path / "out.json"
    order: list[str] = []

    stats = run_plan(
        lambda: [
            TaskSpec(
                key="blocked",
                target=target,
                needs=(missing,),
                run=lambda: _publish(target, order, "blocked"),
            )
        ],
        worker_id="w0",
    )

    assert stats.completed == 0
    assert not target.exists()
