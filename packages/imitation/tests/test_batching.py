"""The batching correctness invariant: merged logits equal per-example ones."""

from __future__ import annotations

import torch

from connections.agent import OnlineIDAgent

from conftest import EITHER_VIA_P, EITHER_VIA_R, collect_examples

from imitation.model import GraphModelConfig, GraphNetwork
from imitation.performance import PerformanceRecipe
from imitation.representation.batch import GraphDataset, collate


def _examples(tmp_path):
    recipe = PerformanceRecipe(agent_class=OnlineIDAgent)
    collected = []
    for name, text in (("via_p.p", EITHER_VIA_P), ("via_r.p", EITHER_VIA_R)):
        problem = tmp_path / name
        problem.write_text(text, encoding="utf-8")
        collected.extend(collect_examples(problem, recipe))
    assert len(collected) >= 2, "both problems pass a real decision"
    return collected


def test_batched_logits_match_per_example_forward(tmp_path):
    examples = _examples(tmp_path)
    dataset = GraphDataset(examples)
    torch.manual_seed(0)
    model = GraphNetwork(GraphModelConfig(hidden_dim=16, message_rounds=2))
    model.eval()

    batch = collate(list(dataset.items))
    with torch.no_grad():
        merged = model.score_batch(batch)
        separate = torch.cat(
            [model(example.model_input) for example in examples]
        )
    assert torch.allclose(merged, separate, atol=1e-5), (
        "disconnected components must compute independently"
    )


def test_matrix_tier_sharing_changes_node_counts_not_logits(tmp_path):
    examples = _examples(tmp_path)
    same_matrix = [e for e in examples if e.problem_path == examples[0].problem_path]
    doubled = GraphDataset([same_matrix[0], same_matrix[0]])
    batch = collate(list(doubled.items))

    single_symbols = doubled.items[0].nodes["symbol"].shape[0]
    assert batch.graph.nodes["symbol"].shape[0] == single_symbols, (
        "one matrix block serves every example that shares its key"
    )

    torch.manual_seed(0)
    model = GraphNetwork(GraphModelConfig(hidden_dim=16, message_rounds=2))
    model.eval()
    with torch.no_grad():
        merged = model.score_batch(batch)
        single = model(same_matrix[0].model_input)
    assert torch.allclose(merged, torch.cat([single, single]), atol=1e-5)
