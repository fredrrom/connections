"""Choosing and dividing the problems a run covers.

A corpus run is reproducible only if the problem list is: the same sources must
give the same problems in the same order on every machine, or a resumed run
would work on a different set than the one it started. Ordering is therefore
explicit and total, never filesystem order, which varies between platforms.

Sharding is deterministic for the same reason -- a shard is identified by its
index, so a worker that dies mid-shard is replaced by one that recomputes
exactly the same slice.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


def glob_anchor(source: str | Path) -> Path:
    """The directory a globbed source is rooted at.

    ``TPTP/Problems/**/*+*.p`` is anchored at ``TPTP/Problems``. Callers need
    this to resolve includes relative to the corpus rather than the cwd.
    """

    text = str(source)
    head = text.split("*", 1)[0]
    anchor = Path(head)
    return anchor if head.endswith("/") or not anchor.suffix else anchor.parent


def select_problems(
    sources: Iterable[str | Path],
    *,
    root: Path | None = None,
    pattern: str = "*.p",
    limit: int | None = None,
    shuffle_seed: int | None = None,
) -> tuple[Path, ...]:
    """Resolve sources to an ordered, de-duplicated problem list.

    A source is a file, a directory (searched with ``pattern``), or a glob. The
    result is sorted, so two machines agree; ``shuffle_seed`` permutes it
    reproducibly, for when a corpus is ordered by difficulty and a prefix would
    be unrepresentative. ``limit`` applies after shuffling, so a truncated run
    is a random sample rather than an alphabetical one.
    """

    found: list[Path] = []
    for source in sources:
        text = str(source)
        if "*" in text:
            # Split the fixed prefix from the pattern so ``**`` is matched by
            # glob rather than taken literally as a directory name.
            anchor = glob_anchor(text)
            relative = str(Path(text).relative_to(anchor))
            base = anchor if root is None else root / anchor
            found.extend(base.glob(relative))
            continue
        base = Path(text) if root is None else root / text
        if base.is_dir():
            found.extend(base.rglob(pattern))
        elif base.is_file():
            found.append(base)

    unique = sorted({path.resolve() for path in found})
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(unique)
    if limit is not None:
        unique = unique[:limit]
    return tuple(unique)


@dataclass(frozen=True, slots=True)
class Shard:
    """A contiguous slice of the problem list, identified by index.

    Contiguous rather than strided so that a shard's problems are adjacent in
    the corpus: TPTP is grouped by domain, and adjacent problems share include
    files, so a worker reuses parsed axioms instead of re-reading them.
    """

    index: int
    problems: tuple[Path, ...]

    def __len__(self) -> int:
        return len(self.problems)


def shard(problems: Sequence[Path], *, size: int) -> tuple[Shard, ...]:
    """Divide problems into shards of at most ``size``.

    Shard membership depends only on the list and the size, so the same call
    always produces the same slices -- which is what lets a killed worker be
    replaced without redistributing anyone else's work.
    """

    if size < 1:
        raise ValueError("shard size must be positive")
    return tuple(
        Shard(index=i, problems=tuple(problems[start : start + size]))
        for i, start in enumerate(range(0, len(problems), size))
    )


__all__ = ["Shard", "glob_anchor", "select_problems", "shard"]
