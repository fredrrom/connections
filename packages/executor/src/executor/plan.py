"""Declaring work: a task names what it produces and what it needs.

An experiment describes its work as tasks, each naming the artifact it
publishes and the artifacts it depends on. Readiness follows from the tree --
a task runs once its inputs exist and its own target does not -- so nothing
declares an order and no stage barrier exists. Two shards of one corpus, and a
training on last iteration's dataset, are runnable at the same moment if their
inputs happen to be there.

The task set is a callable rather than a list because it grows: shards are only
known once a corpus is partitioned, and iteration k+1 only makes sense once k
exists. Re-evaluating it each pass is what lets work appear mid-run, which is
also what an online learner needs.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from executor.worker import DrainStats, drain


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """One unit of work: what it publishes, what it needs, and how to do it.

    ``run`` must publish ``target`` atomically -- see `executor.artifact`. It is
    passed no arguments; an experiment closes over whatever context it needs.
    """

    key: str
    target: Path
    run: Callable[[], None]
    needs: tuple[Path, ...] = field(default=())

    @property
    def done(self) -> bool:
        return self.target.exists()

    @property
    def blocked(self) -> bool:
        return any(not need.exists() for need in self.needs)

    @property
    def ready(self) -> bool:
        return not self.done and not self.blocked


def ready_tasks(tasks: Iterable[TaskSpec]) -> list[TaskSpec]:
    return [task for task in tasks if task.ready]


def run_plan(
    tasks: Callable[[], Iterable[TaskSpec]],
    *,
    worker_id: str,
    stop: Callable[[], bool] | None = None,
    idle_sleep: float = 5.0,
) -> DrainStats:
    """Drain a declared plan until nothing is left to do.

    Returns when every task is either published or blocked on an input no one
    is producing. A worker that finds only blocked tasks stops rather than
    waiting: if the input is coming from another worker, the caller re-enters,
    and if it is not, waiting forever would hide the fault.
    """

    return drain(
        lambda: ready_tasks(tasks()),
        lambda task: task.run(),
        worker_id=worker_id,
        stop=stop,
        idle_sleep=idle_sleep,
    )


__all__ = ["TaskSpec", "ready_tasks", "run_plan"]
