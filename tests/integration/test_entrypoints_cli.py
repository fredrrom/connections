from __future__ import annotations

import os
import subprocess
import sys


def _env_without_logic_roots() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("TPTP", None)
    env.pop("ILTP", None)
    env.pop("QMLTP", None)
    return env


def test_pycop_console_help_runs():
    proc = subprocess.run(
        ["pycop", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=os.environ.copy(),
    )
    assert proc.returncode == 0
    assert "Connections Python connection-tableau prover" in proc.stdout


def test_all_prover_helps_include_steps_option():
    proc = subprocess.run(
        ["pycop", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=os.environ.copy(),
    )
    assert proc.returncode == 0
    assert "--steps" in proc.stdout
    assert "--timeout" in proc.stdout
    assert "--source-dir" in proc.stdout
    assert "--trace-search" in proc.stdout
    assert "--trace-clausification" in proc.stdout


def test_pycop_accepts_explicit_source_dir_without_tptp_env(tmp_path):
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "axioms.ax").write_text("fof(a1,axiom,p).\n", encoding="utf-8")
    problem = tmp_path / "theorem.p"
    problem.write_text("include('axioms.ax').\nfof(c,conjecture,p).\n", encoding="utf-8")
    env = _env_without_logic_roots()

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--source-dir",
            str(lib_dir),
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )

    assert proc.returncode == 0
    assert "Theorem" in proc.stdout


def test_pycop_reports_satisfiable_when_no_start_clause_exists(tmp_path):
    problem = tmp_path / "tiny.p"
    problem.write_text("fof(a1,axiom,~p).\n", encoding="utf-8")
    env = _env_without_logic_roots()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    assert proc.returncode == 0
    assert "Satisfiable" in proc.stdout


def test_pycop_supports_intuitionistic_matrix_construction(tmp_path):
    problem = tmp_path / "tiny.p"
    problem.write_text("fof(c,conjecture,(p => p)).\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "intuitionistic",
            "constant",
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=_env_without_logic_roots(),
    )

    assert proc.returncode == 0
    assert "Theorem" in proc.stdout


def test_pycop_supports_modal_matrix_construction(tmp_path):
    problem = tmp_path / "tiny_modal.p"
    problem.write_text("qmf(c,conjecture,(#box:p => #box:p)).\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "D",
            "cumulative",
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=_env_without_logic_roots(),
    )

    assert proc.returncode == 0
    assert "Theorem" in proc.stdout


def test_pycop_reports_counter_satisfiable_for_counterexample_problem(tmp_path):
    problem = tmp_path / "counterexample.p"
    problem.write_text("fof(a1,axiom,p).\nfof(c,conjecture,q).\n", encoding="utf-8")
    env = _env_without_logic_roots()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    assert proc.returncode == 0
    assert "CounterSatisfiable" in proc.stdout
    assert "GaveUp" not in proc.stdout


def test_pycop_reports_unsatisfiable_for_closed_cnf_with_negated_conjecture(
    tmp_path,
):
    problem = tmp_path / "unsat_cnf.p"
    problem.write_text(
        "cnf(c1,axiom,p).\ncnf(c2,negated_conjecture,~p).\n",
        encoding="utf-8",
    )
    env = _env_without_logic_roots()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )

    assert proc.returncode == 0
    assert "Unsatisfiable" in proc.stdout
    assert "Theorem" not in proc.stdout


def test_pycop_reports_satisfiable_for_exhausted_cnf_with_negated_conjecture(
    tmp_path,
):
    problem = tmp_path / "sat_cnf.p"
    problem.write_text(
        "cnf(c1,negated_conjecture,p).\n",
        encoding="utf-8",
    )
    env = _env_without_logic_roots()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--steps",
            "20",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )

    assert proc.returncode == 0
    assert "Satisfiable" in proc.stdout
    assert "CounterSatisfiable" not in proc.stdout


def test_pycop_schedule_prints_strategy_status_without_trace(tmp_path):
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    schedule = tmp_path / "schedule.json"
    schedule.write_text('[{"settings":["cut"],"weight":1}]', encoding="utf-8")
    env = _env_without_logic_roots()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--schedule",
            str(schedule),
            "--steps",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    assert proc.returncode == 0
    assert "strategy 1:" in proc.stdout
    assert "GaveUp" in proc.stdout


def test_pycop_default_cli_runs_single_strategy(tmp_path):
    problem = tmp_path / "non_theorem.p"
    problem.write_text(
        "fof(a1,axiom,p).\nfof(c,conjecture,q).\n",
        encoding="utf-8",
    )
    env = _env_without_logic_roots()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "connections.pycop.cli",
            str(problem),
            "classical",
            "constant",
            "--trace-search",
            "--steps",
            "60",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    action_lines = [
        line
        for line in proc.stdout.splitlines()
        if line in {"start", "extension", "reduction", "lemma", "backtrack"}
    ]
    assert proc.returncode == 0
    assert "strategy 1:" not in proc.stdout
    assert action_lines == ["start", "backtrack"]
    assert "CounterSatisfiable" in proc.stdout
