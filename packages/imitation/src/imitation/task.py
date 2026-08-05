"""What the imitation needs to know about a unit of work: almost nothing.

A task is identified by the artifact it publishes and a key naming the kind of
work. Everything else -- what corpus, which policy, which iteration, what the
task actually does -- belongs to the experiment that defines it, and the
imitation never learns any of it.

`Task` is a Protocol rather than a base class so an experiment can use its own
richer type without inheriting from here. A `Chain(corpus, profile, policy)`
carrying an iteration index satisfies it as long as it exposes ``key`` and
``target``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Task(Protocol):
    """A unit of claimable work."""

    @property
    def key(self) -> str:
        """Stable name for this work, unique among tasks sharing a directory.

        Used to derive claim and attempt paths, so it must not collide with a
        sibling task's key and must be stable across restarts -- a key that
        changed between runs would orphan the previous claim.
        """

    @property
    def target(self) -> Path:
        """The artifact this task publishes. Its existence means 'done'."""


def is_done(task: Task) -> bool:
    """Whether the task's artifact has been published.

    Readiness -- whether a task's *inputs* exist -- is the experiment's
    business, because only it knows what depends on what. Completion is not:
    an artifact either exists or does not.
    """

    return task.target.exists()


__all__ = ["Task", "is_done"]
