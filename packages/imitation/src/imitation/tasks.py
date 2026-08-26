"""Task assignment: the harness's enumeration of p_Omega.

Which problem to attempt next is the environment's draw, not the agent's
choice: the corpus is the task distribution, and this module enumerates it
-- one episode per problem per round, n = 1 per omega. The holdout split is
the seam for generalization and transfer measurement, both of which happen
above the agent.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from connections.interaction.run import Problem


@dataclass(frozen=True, slots=True)
class EpisodeTask:
    """One episode: a task omega, the budgets, and which attempt this is.

    ``trajectory_index`` numbers the episodes a pass spends on one problem;
    more than one per pass only earns its compute under a stochastic
    chooser, and it is what the conditional measures' estimation needs.
    """

    problem: Problem
    round_index: int
    step_limit: int | None = None
    timeout_seconds: float | None = None
    trajectory_index: int = 0


def holdout_split(
    problems: Sequence[Problem],
    *,
    holdout_fraction: float,
    seed: int,
) -> tuple[tuple[Problem, ...], tuple[Problem, ...]]:
    """Deterministic train/holdout partition of a corpus."""

    if not 0.0 <= holdout_fraction <= 1.0:
        raise ValueError("holdout_fraction must be within [0, 1]")
    shuffled = list(problems)
    random.Random(seed).shuffle(shuffled)
    held = round(len(shuffled) * holdout_fraction)
    return tuple(shuffled[held:]), tuple(shuffled[:held])


__all__ = ["EpisodeTask", "holdout_split"]
