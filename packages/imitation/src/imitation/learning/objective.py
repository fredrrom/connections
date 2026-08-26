"""The imitation objective: variable-arity softmax cross-entropy.

A batch's logits are one flat concatenation of every example's candidate
scores; ``action_counts`` segments it. Per segment the loss is
logsumexp - logit[chosen]: behaviour cloning over a per-state variable-size
action set, and each term a bound on that trajectory's probability under
the policy.
"""

from __future__ import annotations

import torch


def segmented_cross_entropy(
    logits: torch.Tensor,
    action_counts: torch.Tensor,
    chosen_indices: torch.Tensor,
    *,
    reduction: str = "mean",
) -> torch.Tensor:
    losses: list[torch.Tensor] = []
    start = 0
    for count, chosen_index in zip(
        action_counts.tolist(),
        chosen_indices.tolist(),
        strict=True,
    ):
        segment = logits[start : start + count]
        losses.append(torch.logsumexp(segment, dim=0) - segment[chosen_index])
        start += count
    stacked = torch.stack(losses)
    if reduction == "mean":
        return stacked.mean()
    if reduction == "sum":
        return stacked.sum()
    raise ValueError(f"unsupported segmented loss reduction: {reduction!r}")


def segmented_accuracy(
    logits: torch.Tensor,
    action_counts: torch.Tensor,
    chosen_indices: torch.Tensor,
) -> int:
    correct = 0
    start = 0
    for count, chosen_index in zip(
        action_counts.tolist(),
        chosen_indices.tolist(),
        strict=True,
    ):
        prediction = int(torch.argmax(logits[start : start + count]))
        correct += int(prediction == chosen_index)
        start += count
    return correct


__all__ = ["segmented_accuracy", "segmented_cross_entropy"]
