"""A learning agent over connections.

Russell and Norvig's learning agent, each component a module: the
performance element is a ``connections`` agent whose chooser is learned
(``performance``), the critic replays found proofs into labeled
demonstrations (``critic``), the learning element fits a graph neural
network to them (``representation``, ``model``, ``learning``), and the
problem generator proposes exploratory actions (degenerate in proof
cloning). Task assignment and evaluation sit above the agent, in ``tasks``
and ``measures``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AllActionsMarkovAgent": "imitation.performance",
    "AttemptMeasures": "imitation.experiment",
    "CheckpointActionModel": "imitation.model",
    "CorpusMeasures": "imitation.experiment",
    "ActorLearnerAgent": "imitation.actor_learner",
    "DAggerAgent": "imitation.actor_learner",
    "EpisodeTask": "imitation.tasks",
    "Example": "imitation.records",
    "ExperimentReport": "imitation.experiment",
    "ModelChooser": "imitation.performance",
    "evaluate": "imitation.experiment",
    "retention": "imitation.experiment",
    "run_experiment": "imitation.experiment",
    "PerformanceRecipe": "imitation.performance",
    "ProofCloningCritic": "imitation.critic",
    "SupervisedLearner": "imitation.learning.trainer",
    "TrainingConfig": "imitation.learning.trainer",
    "aggregate": "imitation.experiment",
    "holdout_split": "imitation.tasks",
    "success_curve": "imitation.experiment",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(name)
    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value
