from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tools.parity.run_matrix_parity import _normalize_generated_names
from tools.parity.run_manifest import _row_failed


ROOT = Path(__file__).resolve().parents[2]
requires_prolog_parity = pytest.mark.skipif(
    os.environ.get("CONNECTIONS_RUN_PROLOG_TESTS") != "1"
    or shutil.which("swipl") is None,
    reason="set CONNECTIONS_RUN_PROLOG_TESTS=1 and install SWI-Prolog",
)


@requires_prolog_parity
def test_status_check_tool_compares_native_status_with_expected_or_reference():
    completed = _run_tool(
        "run_status_check.py",
        "--json",
        "--case",
        "classical_tautology",
        "--case",
        "classical_open_atom",
        "--case",
        "intuitionistic_tautology",
        "--case",
        "modal_s5_diamond_implies_box_diamond",
    )

    rows = _json_rows(completed.stdout)
    assert [row["name"] for row in rows] == [
        "classical_tautology",
        "classical_open_atom",
        "intuitionistic_tautology",
        "modal_s5_diamond_implies_box_diamond",
    ]
    assert all(row["status_match"] is True for row in rows)


@requires_prolog_parity
def test_trace_parity_tool_compares_reference_and_native_pycop():
    completed = _run_tool(
        "run_trace_parity.py",
        "--json",
        "--case",
        "classical_tautology",
        "--case",
        "intuitionistic_tautology",
        "--case",
        "modal_s5_diamond_implies_box_diamond",
        "--case",
        "classical_open_atom_comp1",
        "--case",
        "intuitionistic_tautology_no_cut",
        "--case",
        "modal_d_box_implies_diamond_no_scut",
    )

    rows = _json_rows(completed.stdout)
    assert [row["name"] for row in rows] == [
        "classical_tautology",
        "intuitionistic_tautology",
        "modal_s5_diamond_implies_box_diamond",
        "classical_open_atom_comp1",
        "intuitionistic_tautology_no_cut",
        "modal_d_box_implies_diamond_no_scut",
    ]
    assert all(row["status_match"] is True for row in rows)
    assert all(row["trace_match"] is True for row in rows)


@requires_prolog_parity
def test_parity_umbrella_tool_runs_quick_release_gate():
    completed = _run_tool("run_all.py", "--json", "--only", "matrix")

    rows = _json_rows(completed.stdout)
    assert [row["name"] for row in rows] == ["matrix"]
    assert rows[0]["passed"] is True
    assert rows[0]["failures"] == 0


def test_manifest_parity_tool_loads_full_0_1_manifest_without_corpus_runs():
    completed = _run_tool(
        "run_manifest.py",
        "--json",
        "--limit",
        "0",
        "--allow-missing",
    )

    rows = _json_rows(completed.stdout)
    sweeps = {row["sweep"] for row in rows}
    assert "classical_tptp_v6_fof" in sweeps
    assert "intuitionistic_iltp_firstorder" in sweeps
    assert "modal_qmltp_d_constant" in sweeps
    assert "modal_qmltp_s5_varying" in sweeps
    assert all(row["schema"] == "connections.parity_manifest_summary.v1" for row in rows)
    assert all(row["rows"] == 0 for row in rows)
    assert all(row["failures"] == 0 for row in rows)


def test_manifest_parity_tool_writes_jsonl_and_summary(tmp_path: Path):
    output = tmp_path / "manifest.jsonl"
    summary_output = tmp_path / "manifest.summary.json"

    _run_tool(
        "run_manifest.py",
        "--limit",
        "0",
        "--allow-missing",
        "--out",
        str(output),
        "--summary-out",
        str(summary_output),
    )

    rows = _json_rows(output.read_text(encoding="utf-8"))
    summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert summary["schema"] == "connections.parity_manifest_run_summary.v1"
    assert summary["output"] == str(output)
    assert summary["summary_output"] == str(summary_output)
    assert summary["sweep_count"] == len(rows)
    assert summary["rows"] == 0
    assert summary["failures"] == 0


def test_matrix_manifest_loads_without_corpus_runs():
    completed = _run_tool(
        "run_manifest.py",
        "--json",
        "--manifest",
        "tools/parity/manifests/matrix-0.1.json",
        "--limit",
        "0",
        "--allow-missing",
    )

    rows = _json_rows(completed.stdout)
    sweeps = {row["sweep"] for row in rows}
    assert "classical_tptp_v6_matrix" in sweeps
    assert "intuitionistic_iltp_firstorder_matrix" in sweeps
    assert "modal_qmltp_s5_varying_matrix" in sweeps
    assert all(row["kind"] == "matrix" for row in rows)
    assert all(row["schema"] == "connections.parity_manifest_summary.v1" for row in rows)


def test_matrix_parity_normalizes_generated_name_counters():
    native = [
        ":([],[:(-(p_defini(8)),-([])),"
        ":(p1(:(f_skolem(7),pre(c_skolem(5),c_skolem(7)))),"
        "[c_skolem(5),c_skolem(7)])])"
    ]
    reference = [
        ":([],[:(-(p_defini(9)),-([])),"
        ":(p1(:(f_skolem(8),pre(c_skolem(6),c_skolem(8)))),"
        "[c_skolem(6),c_skolem(8)])])"
    ]

    assert _normalize_generated_names(native) == _normalize_generated_names(reference)


def test_matrix_parity_normalizes_leancop_conjecture_marker():
    native = ["[accept_team(countrya,countryb,towna,n6)]"]
    reference = [
        "[#,accept_team(countrya,countryb,towna,n6)]",
        "[-(#)]",
    ]

    assert _normalize_generated_names(native) == _normalize_generated_names(reference)


def test_manifest_classifies_shared_timeout_against_expected():
    row = {
        "expected_status": "Theorem",
        "native_expected_match": False,
        "native_status": "Timeout",
        "reference_status": "Timeout",
        "status_match": True,
    }

    assert _row_failed(row) is False


def test_manifest_keeps_unexpected_non_timeout_status_as_failure():
    row = {
        "expected_status": "Theorem",
        "native_expected_match": False,
        "native_status": "CounterSatisfiable",
        "reference_status": "Theorem",
        "status_match": False,
    }

    assert _row_failed(row) is True


def test_manifest_classifies_native_reference_unexpected_agreement():
    row = {
        "expected_status": "Theorem",
        "native_expected_match": False,
        "native_status": "CounterSatisfiable",
        "reference_status": "CounterSatisfiable",
        "status_match": True,
    }

    assert _row_failed(row) is False


@requires_prolog_parity
def test_path_parity_tools_resolve_tptp_source_dir(tmp_path: Path):
    tptp_root = tmp_path / "TPTP-root"
    axioms = tptp_root / "Axioms"
    problems = tptp_root / "Problems" / "SYN"
    axioms.mkdir(parents=True)
    problems.mkdir(parents=True)
    (axioms / "SYN000+0.ax").write_text("fof(ax,axiom,p).\n", encoding="utf-8")
    problem = problems / "SYN000+1.p"
    problem.write_text(
        "include('Axioms/SYN000+0.ax').\nfof(c,conjecture,p).\n",
        encoding="utf-8",
    )

    status = _run_tool(
        "run_status_check.py",
        "--json",
        "--path",
        str(problem),
        "--source-dir",
        str(tptp_root),
        "--settings",
        "cut",
        "--settings",
        "comp(7)",
    )
    trace = _run_tool(
        "run_trace_parity.py",
        "--json",
        "--path",
        str(problem),
        "--source-dir",
        str(tptp_root),
        "--settings",
        "cut",
        "--settings",
        "comp(7)",
    )

    status_row = _json_rows(status.stdout)[0]
    trace_row = _json_rows(trace.stdout)[0]
    assert status_row["status_match"] is True
    assert trace_row["status_match"] is True
    assert trace_row["trace_match"] is True
    assert status_row["source_file_dirs"] == [str(tptp_root.resolve())]


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "parity" / args[0]), *args[1:]],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return completed


def _json_rows(output: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]
