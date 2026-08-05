"""Mutual exclusion between workers, with no coordinator.

A worker claims a task by creating a directory; `mkdir` is atomic, so exactly
one of several racing workers succeeds. Ownership is refreshed by touching a
file inside the claim, and a claim whose owner has stopped touching it becomes
reclaimable. No process holds the authoritative state: it is entirely on disk,
so workers can be added or killed at any time.

Claims are advisory. Correctness rests on the atomic commit in `artifact`, not
on the claim: losing a claim mid-task is harmless, because publication still
either wins the rename or discards the work. The claim only avoids duplicated
effort.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import time
import uuid
from pathlib import Path

# A claim untouched for this long may be taken over: long enough that a slow
# task is not stolen from a living worker, short enough that a dead node's work
# is picked up within one coffee break.
CLAIM_STALE_SECONDS = 600.0


def _claim_dir(target: Path, key: str) -> Path:
    return target.parent / f".claim_{key}"


def _attempts_dir(target: Path, key: str) -> Path:
    return target.parent / f".attempts_{key}"


def _stage_claim(target: Path, key: str, worker_id: str) -> Path:
    """Build a complete claim under a temporary name in the same directory."""

    staged = target.parent / f".tmp.claim_{key}.{uuid.uuid4().hex[:8]}"
    staged.mkdir(parents=True)
    (staged / "owner.json").write_text(
        json.dumps(
            {
                "worker": worker_id,
                "host": socket.gethostname(),
                "pid": os.getpid(),
                "claimed_at": time.time(),
            }
        ),
        encoding="utf-8",
    )
    return staged


def _install(staged: Path, claim: Path) -> bool:
    """Move a staged claim into place; False if someone claimed first.

    Renaming onto an existing directory fails because a claim always contains
    its owner file -- which is exactly why the claim is staged complete rather
    than created empty and filled in.
    """

    try:
        os.rename(staged, claim)
        return True
    except OSError:
        shutil.rmtree(staged, ignore_errors=True)
        return False


def try_claim(target: Path, key: str, worker_id: str) -> bool:
    """Claim the task producing ``target``; False if another worker owns it.

    Both taking a free claim and reclaiming a stale one are single atomic
    renames, so concurrent workers cannot tear each other's claims: a claim is
    never visible in a partial state, and exactly one reclaimer can move a
    stale claim aside.
    """

    claim = _claim_dir(target, key)
    claim.parent.mkdir(parents=True, exist_ok=True)

    staged = _stage_claim(target, key, worker_id)
    if _install(staged, claim):
        return True

    # Occupied. Take it over only if its owner stopped refreshing it.
    try:
        age = time.time() - (claim / "owner.json").stat().st_mtime
    except OSError:
        # Either the claim vanished between our rename and this check, or it is
        # mid-reclaim by someone else. Both resolve on the next pass.
        return False
    if age <= CLAIM_STALE_SECONDS:
        return False

    # Move the stale claim aside; the rename admits exactly one reclaimer.
    dead = target.parent / f".dead.claim_{key}.{uuid.uuid4().hex[:8]}"
    try:
        os.rename(claim, dead)
    except OSError:
        return False
    shutil.rmtree(dead, ignore_errors=True)

    return _install(_stage_claim(target, key, worker_id), claim)


def heartbeat(target: Path, key: str) -> bool:
    """Refresh ownership. False means the claim was reclaimed underneath us.

    Continuing is safe: the commit either wins its rename or is discarded.
    """

    try:
        os.utime(_claim_dir(target, key) / "owner.json")
        return True
    except OSError:
        return False


def release(target: Path, key: str) -> None:
    shutil.rmtree(_claim_dir(target, key), ignore_errors=True)


def record_attempt(target: Path, key: str, error: str) -> None:
    """Record a failed attempt beside the task, so repeat failures are visible.

    Attempts accumulate rather than overwrite: a task that fails on every worker
    is a different problem from one that failed once on a bad node.
    """

    attempts = _attempts_dir(target, key)
    attempts.mkdir(parents=True, exist_ok=True)
    stamp = f"{int(time.time())}_{uuid.uuid4().hex[:6]}.json"
    (attempts / stamp).write_text(
        json.dumps(
            {
                "at": time.time(),
                "host": socket.gethostname(),
                "error": error[-4000:],
            }
        ),
        encoding="utf-8",
    )


def attempt_count(target: Path, key: str, *, within_seconds: float | None = None) -> int:
    """How many attempts failed, optionally only counting recent ones."""

    attempts = _attempts_dir(target, key)
    if not attempts.is_dir():
        return 0
    if within_seconds is None:
        return sum(1 for _ in attempts.glob("*.json"))
    cutoff = time.time() - within_seconds
    count = 0
    for path in attempts.glob("*.json"):
        try:
            if path.stat().st_mtime >= cutoff:
                count += 1
        except OSError:
            continue
    return count


__all__ = [
    "CLAIM_STALE_SECONDS",
    "attempt_count",
    "heartbeat",
    "record_attempt",
    "release",
    "try_claim",
]
