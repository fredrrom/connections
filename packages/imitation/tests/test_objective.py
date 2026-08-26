"""The segmented objective agrees with the dense one where both exist."""

from __future__ import annotations

import pytest
import torch
import torch.nn.functional as F

from imitation.learning.objective import segmented_accuracy, segmented_cross_entropy


def test_equal_arity_segments_match_dense_cross_entropy():
    logits = torch.tensor([1.0, 2.0, 3.0, 0.5, 0.1, 0.4])
    counts = torch.tensor([3, 3])
    chosen = torch.tensor([2, 0])

    segmented = segmented_cross_entropy(logits, counts, chosen)
    dense = F.cross_entropy(logits.reshape(2, 3), chosen)
    assert torch.isclose(segmented, dense)


def test_variable_arity_segments_are_each_their_own_softmax():
    logits = torch.tensor([0.0, 1.0, 2.0, 3.0, 4.0])
    counts = torch.tensor([2, 3])
    chosen = torch.tensor([1, 0])

    total = segmented_cross_entropy(logits, counts, chosen, reduction="sum")
    first = F.cross_entropy(logits[:2].reshape(1, 2), chosen[:1])
    second = F.cross_entropy(logits[2:].reshape(1, 3), chosen[1:])
    assert torch.isclose(total, first + second)


def test_mean_reduction_averages_over_examples_not_candidates():
    logits = torch.tensor([0.0, 1.0, 2.0, 3.0, 4.0])
    counts = torch.tensor([2, 3])
    chosen = torch.tensor([1, 0])

    mean = segmented_cross_entropy(logits, counts, chosen, reduction="mean")
    total = segmented_cross_entropy(logits, counts, chosen, reduction="sum")
    assert torch.isclose(mean, total / 2)


def test_an_unknown_reduction_is_an_error():
    with pytest.raises(ValueError):
        segmented_cross_entropy(
            torch.tensor([0.0]),
            torch.tensor([1]),
            torch.tensor([0]),
            reduction="median",
        )


def test_accuracy_counts_argmax_hits_per_segment():
    logits = torch.tensor([1.0, 5.0, 0.0, 9.0, 2.0])
    counts = torch.tensor([2, 3])
    chosen = torch.tensor([1, 2])

    assert segmented_accuracy(logits, counts, chosen) == 1
