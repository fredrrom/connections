"""Trainer mechanics: stopping, checkpointing, loading, pickling."""

from __future__ import annotations

import pickle

import pytest
import torch

from connections.agent import OnlineIDAgent

from conftest import EITHER_VIA_P, EITHER_VIA_R, collect_examples

from imitation.learning.trainer import TrainingConfig, train
from imitation.model import (
    CheckpointActionModel,
    GraphModelConfig,
    GraphNetwork,
    load_action_model,
)
from imitation.performance import PerformanceRecipe
from imitation.representation.batch import GraphDataset


def _dataset(tmp_path) -> GraphDataset:
    recipe = PerformanceRecipe(agent_class=OnlineIDAgent)
    problem = tmp_path / "via_p.p"
    problem.write_text(EITHER_VIA_P, encoding="utf-8")
    return GraphDataset(collect_examples(problem, recipe))


def _model() -> GraphNetwork:
    torch.manual_seed(0)
    return GraphNetwork(GraphModelConfig(hidden_dim=16, message_rounds=2))


def test_an_empty_dataset_refuses_to_train(tmp_path):
    with pytest.raises(ValueError):
        train(GraphDataset([]), model=_model(), output_dir=tmp_path / "out")


def test_a_met_accuracy_target_stops_training(tmp_path):
    report = train(
        _dataset(tmp_path),
        model=_model(),
        config=TrainingConfig(epochs=50, target_train_accuracy=0.0),
        output_dir=tmp_path / "out",
    )
    assert report.stopped_reason == "target_train_accuracy"
    assert report.epochs == 1, "a trivially met target stops after one epoch"


def test_a_stalled_loss_stops_on_patience(tmp_path):
    report = train(
        _dataset(tmp_path),
        model=_model(),
        config=TrainingConfig(epochs=50, learning_rate=0.0, patience=1),
        output_dir=tmp_path / "out",
    )
    assert report.stopped_reason == "train_loss_convergence"
    assert report.epochs < 50


def test_the_checkpoint_round_trips_to_identical_scores(tmp_path):
    dataset = _dataset(tmp_path)
    out = tmp_path / "out"
    report = train(
        dataset,
        model=_model(),
        config=TrainingConfig(epochs=2),
        output_dir=out,
    )
    assert (out / "model.pt").exists()
    assert (out / "metrics.json").exists()
    assert report.surface_key == dataset.surface_key

    loaded = load_action_model(out)
    example = dataset.examples[0]
    index = loaded(example.model_input)
    assert 0 <= index < len(example.model_input.actions)
    assert loaded(example.model_input) == index, "inference is deterministic"


def test_a_checkpoint_action_model_pickles_before_and_after_loading(tmp_path):
    dataset = _dataset(tmp_path)
    out = tmp_path / "out"
    train(
        dataset,
        model=_model(),
        config=TrainingConfig(epochs=1),
        output_dir=out,
    )
    lazy = CheckpointActionModel(out)
    clone = pickle.loads(pickle.dumps(lazy))

    example = dataset.examples[0]
    first = clone(example.model_input)
    assert 0 <= first < len(example.model_input.actions)
    reclone = pickle.loads(pickle.dumps(clone))
    assert reclone(example.model_input) == first, (
        "pickling a loaded model drops the weights but not the behavior"
    )


def test_a_dataset_refuses_mixed_surfaces(tmp_path):
    narrow = PerformanceRecipe(agent_class=OnlineIDAgent)
    problem_p = tmp_path / "via_p.p"
    problem_p.write_text(EITHER_VIA_P, encoding="utf-8")
    problem_r = tmp_path / "via_r.p"
    problem_r.write_text(EITHER_VIA_R, encoding="utf-8")

    from connections.agent import AgentOptions

    other = PerformanceRecipe(
        agent_class=OnlineIDAgent, options=AgentOptions(cut=True)
    )
    mixed = [*collect_examples(problem_p, narrow), *collect_examples(problem_r, other)]
    with pytest.raises(ValueError, match="mix action surfaces"):
        GraphDataset(mixed)
