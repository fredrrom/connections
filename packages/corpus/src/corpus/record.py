"""What one problem attempt records.

Every prover here answers the same question about a problem -- what happened,
how much did it cost -- so that much is fixed. What each prover wants to keep
beyond it is not: imitation attaches proof paths, satcop unsat cores and reset
reasons, pycop nothing at all. The envelope is therefore fixed and small, and
anything prover-specific lives in an opaque ``payload`` that nothing here reads.

Records are written as JSON lines: appendable, readable while a run is still
going, and recoverable line by line if a worker is killed mid-write.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Attempt:
    """One prover, one problem, one outcome.

    ``policy`` names whatever produced the actions -- a strategy name, a model
    version, a git sha. The orchestration never interprets it; it exists so a
    record can be traced back to the thing that made it, which is the failure
    the paper's converged runs actually hit.
    """

    problem: str
    status: str | None                  # SZS status, if the prover reached one
    outcome: str | None                 # prover-side outcome (Proved, Timeout, ...)
    steps: int
    elapsed_seconds: float
    policy: str | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def solved(self) -> bool:
        """Whether this attempt produced a proof.

        Deliberately narrow: only a proof-producing status counts. Exhausting
        the search space is a legitimate answer about the problem but not a
        proof, and conflating the two is how a coverage number stops meaning
        what it says.
        """

        return self.status in {"Theorem", "Unsatisfiable", "ContradictoryAxioms"}

    def to_json(self) -> str:
        return json.dumps(
            {
                "problem": self.problem,
                "status": self.status,
                "outcome": self.outcome,
                "steps": self.steps,
                "elapsed_seconds": self.elapsed_seconds,
                "policy": self.policy,
                "error": self.error,
                "payload": self.payload,
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, line: str) -> Attempt:
        data = json.loads(line)
        return cls(
            problem=data["problem"],
            status=data.get("status"),
            outcome=data.get("outcome"),
            steps=data.get("steps", 0),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
            policy=data.get("policy"),
            error=data.get("error"),
            payload=data.get("payload", {}),
        )


def write_attempts(path: Path, attempts: list[Attempt]) -> None:
    """Write attempts as JSON lines. Callers publish the file atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{attempt.to_json()}\n" for attempt in attempts), encoding="utf-8"
    )


def read_attempts(path: Path) -> list[Attempt]:
    """Read attempts, skipping a torn final line.

    A shard is published atomically, so a torn line should not occur; tolerating
    it means a partially written file left by a kill can still be inspected
    rather than raising while someone is debugging a dead run.
    """

    attempts: list[Attempt] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            attempts.append(Attempt.from_json(line))
        except json.JSONDecodeError:
            break
    return attempts


@dataclass(frozen=True, slots=True)
class Summary:
    attempted: int
    solved: int
    errored: int
    total_steps: int
    total_seconds: float

    @property
    def mean_steps(self) -> float:
        """Mean steps over *solved* attempts.

        Averaging over failures too would mostly measure the step budget, since
        an unsolved run stops at the limit rather than where the search gave up.
        """

        return self.total_steps / self.solved if self.solved else 0.0

    def to_json(self) -> str:
        return json.dumps(
            {
                "attempted": self.attempted,
                "solved": self.solved,
                "errored": self.errored,
                "total_steps": self.total_steps,
                "total_seconds": self.total_seconds,
                "mean_steps_solved": self.mean_steps,
            },
            sort_keys=True,
        )


def summarize(attempts: list[Attempt]) -> Summary:
    solved = [attempt for attempt in attempts if attempt.solved]
    return Summary(
        attempted=len(attempts),
        solved=len(solved),
        errored=sum(1 for attempt in attempts if attempt.error is not None),
        total_steps=sum(attempt.steps for attempt in solved),
        total_seconds=sum(attempt.elapsed_seconds for attempt in attempts),
    )


__all__ = [
    "Attempt",
    "Summary",
    "read_attempts",
    "summarize",
    "write_attempts",
]
