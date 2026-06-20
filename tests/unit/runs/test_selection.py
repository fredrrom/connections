from __future__ import annotations

from connections.runs import select_problem_paths


def test_select_problem_paths_applies_offset_after_sort(tmp_path):
    for name in ("c.p", "a.p", "b.p"):
        (tmp_path / name).write_text("fof(c,conjecture,p).\n", encoding="utf-8")

    selected = select_problem_paths((tmp_path,), offset=1, limit=1)

    assert [path.name for path in selected] == ["b.p"]
