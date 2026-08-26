"""The schema's acceptance gate: fixture proofs overfit to full accuracy.

Failure here indicts the schema, not the optimizer: if the representation
cannot separate a handful of demonstrated choices, no amount of training
data will save it.
"""

from __future__ import annotations

import torch

from connections.agent import OnlineIDAgent

from conftest import EITHER_VIA_P, EITHER_VIA_R, collect_examples

from imitation.learning.trainer import TrainingConfig, train
from imitation.model import GraphModelConfig, GraphNetwork
from imitation.performance import PerformanceRecipe
from imitation.representation.batch import GraphDataset


def test_demonstrations_from_two_matrices_overfit_to_full_accuracy(tmp_path):
    recipe = PerformanceRecipe(agent_class=OnlineIDAgent)
    examples = []
    for name, text in (("via_p.p", EITHER_VIA_P), ("via_r.p", EITHER_VIA_R)):
        problem = tmp_path / name
        problem.write_text(text, encoding="utf-8")
        examples.extend(collect_examples(problem, recipe))
    dataset = GraphDataset(examples)

    torch.manual_seed(0)
    # Three message rounds minimum: the signal separating the candidates (a
    # complement edge on a sibling literal) is three hops from the scored
    # target literal.
    model = GraphNetwork(GraphModelConfig(hidden_dim=32, message_rounds=3))
    report = train(
        dataset,
        model=model,
        config=TrainingConfig(
            epochs=200,
            batch_size=8,
            learning_rate=5e-3,
            target_train_accuracy=1.0,
        ),
        output_dir=tmp_path / "out",
    )
    assert report.best_train_accuracy == 1.0, (
        "the schema must separate the demonstrated choices"
    )
    assert report.stopped_reason == "target_train_accuracy"
