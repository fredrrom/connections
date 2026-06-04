from __future__ import annotations

import random
from pathlib import Path
from typing import Sequence


def select_problem_paths(
    roots: Sequence[str | Path],
    *,
    pattern: str = "*.p",
    recursive: bool = True,
    limit: int | None = None,
    offset: int = 0,
    shuffle: bool = False,
    seed: int = 0,
) -> tuple[Path, ...]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if offset < 0:
        raise ValueError("offset must be non-negative")

    paths: list[Path] = []
    for root in roots:
        paths.extend(_paths_from_root(Path(root), pattern=pattern, recursive=recursive))

    unique = sorted({path.resolve() for path in paths})
    if shuffle:
        random.Random(seed).shuffle(unique)
    if offset:
        unique = unique[offset:]
    if limit is not None:
        unique = unique[:limit]
    return tuple(unique)


def _paths_from_root(root: Path, *, pattern: str, recursive: bool) -> tuple[Path, ...]:
    if root.is_file():
        return (root,)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise ValueError(f"problem root is neither a file nor directory: {root}")
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    return tuple(path for path in iterator if path.is_file())


__all__ = ["select_problem_paths"]
