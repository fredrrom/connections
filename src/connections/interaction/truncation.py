"""Why a rollout was cut off, when it was.

An episode ends one of two ways: the agent finishes and its status says why,
or a budget truncates it. ``None`` means not truncated -- the agent's own end.
"""

from __future__ import annotations

from enum import Enum


class Truncation(Enum):
    STEPS = "steps"
    TIME = "time"


__all__ = ["Truncation"]
