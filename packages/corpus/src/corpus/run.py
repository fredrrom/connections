"""Running a prover over a corpus.

This is the shape every experiment starts from: take a problem list, attempt
each problem, keep what happened. Sharding makes it restartable and parallel --
a shard is the unit of work a worker claims, and a published shard is never
recomputed.

What a prover *is* never appears here. The caller supplies a callable from
problem path to `Attempt`, so the same machinery runs pycop, satcop, or a
learned policy, and none of them need to know about each other.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from executor import commit_file, new_tmp
from executor.plan import TaskSpec

from corpus.record import Attempt, read_attempts, summarize, write_attempts
from corpus.selection import Shard, shard

# A problem is attempted by calling this. Raising is allowed: the shard fails,
# is recorded as an attempt, and another worker retries it.
Prover = Callable[[Path], Attempt]


@dataclass(frozen=True, slots=True)
class CorpusRun:
    """A sharded corpus run rooted at a directory.

    The directory is the entire state: which shards exist says what is done, so
    a run resumes by being pointed at the same root, on any machine.
    """

    root: Path
    problems: tuple[Path, ...]
    shard_size: int = 50

    @property
    def shards(self) -> tuple[Shard, ...]:
        return shard(self.problems, size=self.shard_size)

    def shard_path(self, index: int) -> Path:
        return self.root / "shards" / f"shard_{index:05d}.jsonl"

    @property
    def summary_path(self) -> Path:
        return self.root / "summary.json"

    def attempts(self) -> list[Attempt]:
        """Every attempt published so far, in shard order."""

        return [
            attempt
            for index in range(len(self.shards))
            if (path := self.shard_path(index)).exists()
            for attempt in read_attempts(path)
        ]

    def tasks(self, prover: Prover) -> list[TaskSpec]:
        """One task per shard, plus a summary that waits for all of them."""

        shard_paths = tuple(self.shard_path(s.index) for s in self.shards)
        specs = [
            TaskSpec(
                key=f"shard_{s.index:05d}",
                target=self.shard_path(s.index),
                run=_shard_runner(self, s, prover),
            )
            for s in self.shards
        ]
        specs.append(
            TaskSpec(
                key="summary",
                target=self.summary_path,
                needs=shard_paths,
                run=_summary_writer(self),
            )
        )
        return specs


def _shard_runner(run: CorpusRun, s: Shard, prover: Prover) -> Callable[[], None]:
    def execute() -> None:
        target = run.shard_path(s.index)
        tmp = new_tmp(target)
        # A prover that raises on one problem must not lose the shard: record
        # the failure as an attempt and carry on, so one malformed problem
        # cannot block a corpus.
        attempts = []
        for problem in s.problems:
            try:
                attempts.append(prover(problem))
            except Exception as error:  # noqa: BLE001 - recorded, not swallowed
                attempts.append(
                    Attempt(
                        problem=problem.name,
                        status=None,
                        outcome="Error",
                        steps=0,
                        elapsed_seconds=0.0,
                        error=f"{type(error).__name__}: {error}",
                    )
                )
        write_attempts(tmp, attempts)
        commit_file(tmp, target)

    return execute


def _summary_writer(run: CorpusRun) -> Callable[[], None]:
    def execute() -> None:
        tmp = new_tmp(run.summary_path)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(summarize(run.attempts()).to_json(), encoding="utf-8")
        commit_file(tmp, run.summary_path)

    return execute


def corpus_run(
    root: Path,
    problems: Sequence[Path],
    *,
    shard_size: int = 50,
) -> CorpusRun:
    return CorpusRun(root=root, problems=tuple(problems), shard_size=shard_size)


__all__ = ["CorpusRun", "Prover", "corpus_run"]
