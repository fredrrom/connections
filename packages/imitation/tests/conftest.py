"""Shared fixtures: the repository's example problems and a symbolic agent."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from connections.agent import AgentOptions, OnlineIDAgent
from connections.environment.actions import Action
from connections.environment.state import State
from connections.interaction.run import Problem
from connections.interaction.strategy import (
    MatrixOptions,
    PolicyOptions,
    Strategy,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def first(state: State, actions: Sequence[Action]) -> Action:
    _ = state
    return actions[0]


def id_agent(**options: Any) -> OnlineIDAgent:
    return OnlineIDAgent(first, AgentOptions(**options))


def id_strategy(**policy_args: Any) -> Strategy:
    return Strategy(
        matrix=MatrixOptions(),
        policy=PolicyOptions(policy_class=id_agent, args=policy_args),
    )


@pytest.fixture
def socrates_problem() -> Problem:
    return Problem(REPO_ROOT / "examples" / "socrates.p")


# A theorem passing one real (two-way) extension decision; the fact picks
# which branch closes, so the two variants label the decision differently.
EITHER_VIA_P = (
    "fof(a0, axiom, p).\n"
    "fof(a1, axiom, p => q).\n"
    "fof(a2, axiom, r => q).\n"
    "fof(goal, conjecture, q).\n"
)
EITHER_VIA_R = (
    "fof(a0, axiom, r).\n"
    "fof(a1, axiom, p => q).\n"
    "fof(a2, axiom, r => q).\n"
    "fof(goal, conjecture, q).\n"
)


def collect_examples(problem_path, recipe, *, steps: int = 200):
    """Run the base agent on a problem and label its proof for the recipe."""

    from connections.interaction.rollout import rollout
    from connections.interaction.run import build_state
    from connections.interaction.strategy import MatrixOptions

    from imitation.critic import ObservationContext, ProofCloningCritic

    critic = ProofCloningCritic(recipe=recipe)
    state = build_state(Problem(problem_path), matrix_options=MatrixOptions())
    attempt = rollout(state, id_agent(), step_limit=steps)
    assert attempt.status is not None, "the fixture proof must close in budget"
    critic.observe(
        attempt.state, ObservationContext(problem_path=str(problem_path))
    )
    assert not critic.failures, critic.failures
    return critic.feedback()
