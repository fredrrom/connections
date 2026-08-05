"""The drain loop: a worker that finds its own work.

There is no scheduler. A worker repeatedly asks the experiment what is ready,
claims what it can, and does it. Workers may be added or killed at any moment,
on any machine, against the same tree; the only shared state is the filesystem.

The experiment supplies two callables and keeps everything it knows to itself:

    ready()      -> tasks whose inputs exist and whose target does not
    run(task)    -> do the work and publish task.target

`run` is never told about claims. Ownership is refreshed from a background
thread for as long as the call takes, so a task lasting hours is not stolen
while a task whose worker died is reclaimed within `CLAIM_STALE_SECONDS`.
"""

from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from imitation.claim import (
    CLAIM_STALE_SECONDS,
    heartbeat,
    record_attempt,
    release,
    try_claim,
)
from imitation.task import Task, is_done


@dataclass(frozen=True, slots=True)
class DrainStats:
    claimed: int = 0
    completed: int = 0
    failed: int = 0

    def _with(self, **kw: int) -> DrainStats:
        return DrainStats(
            claimed=kw.get("claimed", self.claimed),
            completed=kw.get("completed", self.completed),
            failed=kw.get("failed", self.failed),
        )


class _Heartbeat:
    """Refresh a claim on a timer for the duration of a `with` block."""

    def __init__(self, target: Path, key: str, period: float) -> None:
        self._target = target
        self._key = key
        self._period = period
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> _Heartbeat:
        def beat() -> None:
            while not self._stop.wait(self._period):
                heartbeat(self._target, self._key)

        self._thread = threading.Thread(target=beat, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


def drain(
    ready: Callable[[], Iterable[Task]],
    run: Callable[[Task], None],
    *,
    worker_id: str,
    stop: Callable[[], bool] | None = None,
    idle_sleep: float = 5.0,
    heartbeat_period: float = CLAIM_STALE_SECONDS / 4,
) -> DrainStats:
    """Claim and run ready tasks until `stop()` or nothing is left.

    Returns when `stop()` is true, or when a full pass over `ready()` claims
    nothing and yields nothing -- the tree is finished or entirely owned by
    other workers.

    A task that raises is recorded as an attempt and left unpublished, so
    another worker will retry it. That is deliberate: transient failures (a bad
    node, a memory spike) should not poison a task permanently, and a task that
    fails everywhere shows up as an accumulating attempt count.
    """

    stats = DrainStats()
    # Tasks that raised during this call. They stay unpublished so another
    # worker -- or a later call -- retries them, but retrying immediately here
    # would spin on a deterministic failure.
    failed_here: set[tuple[Path, str]] = set()

    while stop is None or not stop():
        pending = [
            task
            for task in ready()
            if not is_done(task) and (task.target, task.key) not in failed_here
        ]
        if not pending:
            return stats

        progressed = False
        for task in pending:
            if stop is not None and stop():
                return stats
            if not try_claim(task.target, task.key, worker_id):
                continue
            # `pending` was a snapshot: another worker may have published this
            # while we worked through the list. Re-check under the claim, or we
            # redo finished work.
            if is_done(task):
                release(task.target, task.key)
                continue
            stats = stats._with(claimed=stats.claimed + 1)
            progressed = True
            try:
                with _Heartbeat(task.target, task.key, heartbeat_period):
                    run(task)
                stats = stats._with(completed=stats.completed + 1)
            except Exception:
                record_attempt(task.target, task.key, traceback.format_exc())
                failed_here.add((task.target, task.key))
                stats = stats._with(failed=stats.failed + 1)
            finally:
                release(task.target, task.key)

        if not progressed:
            # Work remains but every piece is owned elsewhere; wait rather than
            # spin, so a second worker joining a busy tree costs nothing.
            time.sleep(idle_sleep)
    return stats


__all__ = ["DrainStats", "drain"]
