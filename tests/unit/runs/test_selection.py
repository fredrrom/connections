from __future__ import annotations

import pytest

from connections.runs import glob_anchor, select_problem_paths


def test_select_problem_paths_applies_offset_after_sort(tmp_path):
    for name in ("c.p", "a.p", "b.p"):
        (tmp_path / name).write_text("fof(c,conjecture,p).\n", encoding="utf-8")

    selected = select_problem_paths((tmp_path,), offset=1, limit=1)

    assert [path.name for path in selected] == ["b.p"]


def test_select_problem_paths_expands_glob_roots(tmp_path):
    problems = tmp_path / "Problems" / "SET"
    problems.mkdir(parents=True)
    (problems / "SET001+1.p").write_text("fof(c,conjecture,p).\n", encoding="utf-8")
    (problems / "SET001-1.p").write_text("cnf(c,negated_conjecture,~p).\n", encoding="utf-8")

    selected = select_problem_paths((tmp_path / "Problems" / "**" / "*+*.p",))

    assert [path.name for path in selected] == ["SET001+1.p"]


def test_glob_roots_matching_nothing_raise(tmp_path):
    with pytest.raises(FileNotFoundError):
        select_problem_paths((tmp_path / "Problems" / "**" / "*+*.p",))


def test_glob_anchor_strips_wildcard_suffix(tmp_path):
    anchor = glob_anchor(tmp_path / "Problems" / "**" / "*+*.p")

    assert anchor == tmp_path / "Problems"
    assert glob_anchor(tmp_path / "Problems") == tmp_path / "Problems"
