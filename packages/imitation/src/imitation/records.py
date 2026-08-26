"""Example records: the critic's feedback, durable as JSONL.

An ``Example`` is one choicepoint on a replayed proof. The chosen action is
not stored separately: it is ``model_input.actions[chosen_index]``, and the
label space is exactly the candidate sequence the chooser was shown, named
by ``surface_key``. JSONL files of examples are the interface between
collection and training, so writes are atomic -- a reader never sees a torn
file.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from imitation.representation.schema import GraphInput


@dataclass(frozen=True, slots=True)
class Example:
    """One learner-facing choice on a replayed proof.

    ``trajectory_step_index`` orders the choice within its replay;
    ``proof_step_index`` names the closed-tableau goal it expanded.
    ``behavior_name`` records which policy found the proof; ``round_index``
    which round of the loop it was found in. Both are provenance --
    identity, for deduplication, is ``choicepoint_key``.
    """

    problem_path: str
    trajectory_step_index: int
    proof_step_index: int
    surface_key: str
    model_input: GraphInput
    chosen_index: int
    round_index: int | None = None
    behavior_name: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayFailure:
    """A proof the critic could not replay. Diagnostic, never repaired."""

    problem_path: str
    surface_key: str
    error_type: str
    message: str
    round_index: int | None = None
    behavior_name: str | None = None


def example_to_json(example: Example) -> dict[str, Any]:
    return {
        "problem_path": example.problem_path,
        "trajectory_step_index": example.trajectory_step_index,
        "proof_step_index": example.proof_step_index,
        "surface_key": example.surface_key,
        "model_input": example.model_input.to_dict(),
        "chosen_index": example.chosen_index,
        "round_index": example.round_index,
        "behavior_name": example.behavior_name,
    }


def example_from_json(payload: Mapping[str, Any]) -> Example:
    return Example(
        problem_path=str(payload["problem_path"]),
        trajectory_step_index=int(payload["trajectory_step_index"]),
        proof_step_index=int(payload["proof_step_index"]),
        surface_key=str(payload["surface_key"]),
        model_input=GraphInput.from_dict(dict(payload["model_input"])),
        chosen_index=int(payload["chosen_index"]),
        round_index=(
            None if payload.get("round_index") is None else int(payload["round_index"])
        ),
        behavior_name=(
            None
            if payload.get("behavior_name") is None
            else str(payload["behavior_name"])
        ),
    )


def choicepoint_key(example: Example) -> tuple[object, ...]:
    """Canonical identity of a choicepoint: same shown decision, same key.

    Identity is the surface plus the decision content -- nodes, edges and
    action rows -- serialized stably. ``metadata`` is excluded: it carries
    process-local provenance such as the matrix key, and identity must
    survive crossing processes.
    """

    graph = example.model_input
    return (
        example.surface_key,
        graph.preprocessor,
        graph.version,
        _stable(graph.nodes),
        _stable(graph.edges),
        _stable(graph.actions),
    )


def dedupe(examples: Iterable[Example]) -> tuple[Example, ...]:
    """Keep the first example per choicepoint, in input order."""

    seen: set[tuple[object, ...]] = set()
    kept: list[Example] = []
    for example in examples:
        key = choicepoint_key(example)
        if key in seen:
            continue
        seen.add(key)
        kept.append(example)
    return tuple(kept)


def write_examples(path: str | Path, examples: Sequence[Example]) -> None:
    """Write examples as JSONL via tmp+replace; readers never see a torn file."""

    output = Path(path)
    tmp = output.with_name(f".{output.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as file:
            for example in examples:
                file.write(json.dumps(example_to_json(example), sort_keys=True))
                file.write("\n")
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)


def read_examples(path: str | Path) -> tuple[Example, ...]:
    with Path(path).open("r", encoding="utf-8") as file:
        return tuple(
            example_from_json(json.loads(line)) for line in file if line.strip()
        )


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


__all__ = [
    "Example",
    "ReplayFailure",
    "choicepoint_key",
    "dedupe",
    "example_from_json",
    "example_to_json",
    "read_examples",
    "write_examples",
]
