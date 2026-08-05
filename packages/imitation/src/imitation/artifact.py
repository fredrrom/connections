"""Atomic publication of artifacts.

The filesystem is the whole state of a run: an artifact exists iff the work
that produces it finished. That only holds if publication is atomic, so every
artifact is built under a temporary name in its final directory and moved into
place with a single rename. A worker killed at any point leaves either the
finished artifact or a stray temporary, never a half-written result.

Same-directory renames are required: `os.rename` is atomic within a filesystem,
not across one, and a temporary elsewhere would degrade to a copy.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


def new_tmp(final: Path) -> Path:
    """A same-directory temporary path whose rename onto ``final`` is atomic."""

    return final.parent / f".tmp.{final.name}.{uuid.uuid4().hex[:8]}"


def commit_dir(tmp: Path, final: Path) -> bool:
    """Publish directory ``tmp`` as ``final``.

    Returns False if someone published first; their result stands and ours is
    discarded. Losing the race is normal, not an error: two workers may hold a
    stale claim on the same task.
    """

    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(tmp, final)
        return True
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        return False


def commit_file(tmp: Path, final: Path) -> bool:
    """Publish file ``tmp`` as ``final``; False if we lost the race."""

    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(tmp, final)
        return True
    except OSError:
        tmp.unlink(missing_ok=True)
        return False


__all__ = ["commit_dir", "commit_file", "new_tmp"]
