from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tools.corpus.selection import select_problem_paths


ROOT = Path(__file__).resolve().parents[2]


def test_select_problem_paths_applies_offset_after_sort(tmp_path):
    for name in ("c.p", "a.p", "b.p"):
        (tmp_path / name).write_text("fof(c,conjecture,p).\n", encoding="utf-8")

    selected = select_problem_paths((tmp_path,), offset=1, limit=1)

    assert [path.name for path in selected] == ["b.p"]


def test_corpus_tool_cli_selects_runs_and_writes_summary(tmp_path):
    theorem = tmp_path / "theorem.p"
    theorem.write_text("fof(a,axiom,p).\nfof(c,conjecture,p).\n", encoding="utf-8")
    counter = tmp_path / "counter.p"
    counter.write_text("fof(a,axiom,p).\nfof(c,conjecture,q).\n", encoding="utf-8")
    ignored = tmp_path / "ignored.txt"
    ignored.write_text("not a problem", encoding="utf-8")
    output = tmp_path / "runs.jsonl"
    summary_output = tmp_path / "runs.summary.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "corpus" / "run.py"),
            str(tmp_path),
            "--out",
            str(output),
            "--steps",
            "20",
            "--no-recursive",
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert [row["problem"] for row in rows] == ["counter.p", "theorem.p"]
    assert [row["status"] for row in rows] == ["CounterSatisfiable", "Theorem"]
    assert summary["output"] == str(output)
    assert summary["summary_output"] == str(summary_output)
    assert summary["problems"] == 2
    assert summary["theorem"] == 1
    assert summary["counter_satisfiable"] == 1
