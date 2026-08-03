"""Filesystem-coordinated task execution.

State lives entirely in the artifact tree: a task is done iff its target
exists, work is claimed by creating a directory, and results are published by
an atomic rename. Nothing else holds authoritative state, so workers can join
or die at any point without a coordinator noticing.

The executor knows nothing about what a task does. An experiment supplies
readiness and a run callable; see `worker.drain`.
"""

from executor.artifact import commit_dir, commit_file, new_tmp
from executor.claim import (
    CLAIM_STALE_SECONDS,
    attempt_count,
    heartbeat,
    record_attempt,
    release,
    try_claim,
)
from executor.plan import TaskSpec, ready_tasks, run_plan
from executor.task import Task, is_done
from executor.worker import DrainStats, drain

__all__ = [
    "CLAIM_STALE_SECONDS",
    "DrainStats",
    "Task",
    "TaskSpec",
    "attempt_count",
    "commit_dir",
    "commit_file",
    "drain",
    "heartbeat",
    "is_done",
    "new_tmp",
    "ready_tasks",
    "run_plan",
    "record_attempt",
    "release",
    "try_claim",
]
