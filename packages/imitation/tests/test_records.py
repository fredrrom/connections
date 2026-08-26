"""The serialization contract: examples round-trip, writes are atomic."""

from __future__ import annotations

from dataclasses import replace

import pytest

from imitation.records import (
    Example,
    choicepoint_key,
    dedupe,
    example_from_json,
    example_to_json,
    read_examples,
    write_examples,
)
from imitation.representation.schema import GraphInput


def _example(*, chosen_index: int = 0, matrix_key: str = "1:1") -> Example:
    return Example(
        problem_path="problems/socrates.p",
        trajectory_step_index=1,
        proof_step_index=0,
        surface_key="id/factorization=unify/start=positive/graph.v1",
        model_input=GraphInput(
            nodes={"symbol": [[0, 1]], "goal": [[1, 0]]},
            edges={"lit_sym": [[0, 0]], "arg_term": [[0, 1, 2]]},
            actions=[[0, 0, 1, 0], [1, 0, 1, 1]],
            metadata={"matrix_key": matrix_key},
        ),
        chosen_index=chosen_index,
        round_index=2,
        behavior_name="base",
    )


def test_example_json_round_trip_is_identity():
    example = _example()
    assert example_from_json(example_to_json(example)) == example


def test_examples_survive_the_file(tmp_path):
    examples = (_example(chosen_index=0), _example(chosen_index=1))
    path = tmp_path / "examples.jsonl"
    write_examples(path, examples)
    assert read_examples(path) == examples


def test_a_failed_write_leaves_no_partial_file(tmp_path):
    class _Poisoned(GraphInput):
        __slots__ = ()

        def to_dict(self):
            raise RuntimeError("collapse mid-write")

    poisoned = Example(
        problem_path="p",
        trajectory_step_index=0,
        proof_step_index=0,
        surface_key="s",
        model_input=_Poisoned(nodes={}, edges={}, actions=[]),
        chosen_index=0,
    )
    path = tmp_path / "examples.jsonl"
    with pytest.raises(RuntimeError):
        write_examples(path, [_example(), poisoned])
    assert not path.exists(), "the torn write never became visible"
    assert list(tmp_path.iterdir()) == [], "no temporary file survives"


def test_choicepoint_key_ignores_provenance_but_not_content():
    same_decision = choicepoint_key(_example(matrix_key="1:1"))
    other_process = choicepoint_key(_example(matrix_key="9:9"))
    assert same_decision == other_process, "metadata is provenance, not identity"

    base = _example()
    different = replace(
        base,
        model_input=GraphInput(
            nodes={"symbol": [[0, 2]], "goal": [[1, 0]]},
            edges=base.model_input.edges,
            actions=base.model_input.actions,
        ),
    )
    assert choicepoint_key(different) != same_decision


def test_dedupe_halves_a_doubled_dataset():
    examples = (_example(), _example(matrix_key="9:9"))
    assert dedupe(examples) == (examples[0],)
