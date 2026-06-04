from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_profile_tool_cli_runs_pycop_and_writes_profile_artifacts(tmp_path):
    corpus = tmp_path / "problems"
    corpus.mkdir()
    (corpus / "demo.p").write_text(
        "fof(a,axiom,p).\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )
    output = tmp_path / "profile"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "profiling" / "run.py"),
            str(corpus),
            "--out",
            str(output),
            "--limit-functions",
            "5",
            "--overwrite",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert (output / "profile.pstats").exists()
    assert (output / "runs.jsonl").exists()
    assert (output / "profile_overview.json").exists()
    assert (output / "profile_functions.jsonl").exists()
    assert (output / "profile_callers.jsonl").exists()
    assert (output / "summary.json").exists()

    runs = [
        json.loads(line)
        for line in (output / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert runs[0]["status"] == "Theorem"
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["overview"]["status_counts"]["Theorem"] == 1
    assert summary["total_calls"] > 0
