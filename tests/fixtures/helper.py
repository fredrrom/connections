from __future__ import annotations

from pathlib import Path


def resolve_problem_path_from_fixture(tptp_root: Path, fixture_path: Path) -> Path:
    problem_name = fixture_path.name
    matches = sorted((tptp_root / "Problems").rglob(problem_name))
    assert matches, f"No TPTP source file found for fixture {fixture_path.name}"
    assert len(matches) == 1, (
        f"Ambiguous TPTP source for fixture {fixture_path.name}: "
        f"{', '.join(str(path) for path in matches)}"
    )
    return matches[0]
