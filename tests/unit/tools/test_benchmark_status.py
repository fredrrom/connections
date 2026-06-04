from __future__ import annotations

from pathlib import Path

from tools.parity.benchmark_status import benchmark_status
from tools.parity.run_status_check import status_check_passed


def test_tptp_status_annotation_maps_to_expected_szs(tmp_path: Path):
    problem = _problem(
        tmp_path,
        """
% Status   : Unsatisfiable
fof(a,axiom,~p).
""",
    )

    status = benchmark_status(problem, logic="classical")

    assert status is not None
    assert status.label == "Unsatisfiable"
    assert status.szs_status == "Unsatisfiable"
    assert status.source == "tptp_status"


def test_iltp_intuitionistic_open_maps_to_counter_satisfiable(tmp_path: Path):
    problem = _problem(
        tmp_path,
        """
% Status   : Theorem
%
% Status (intuit.) : Open (Problem negated)
fof(c,conjecture,p).
""",
    )

    status = benchmark_status(problem, logic="intuitionistic")

    assert status is not None
    assert status.label == "Open (Problem negated)"
    assert status.szs_status == "CounterSatisfiable"
    assert status.source == "iltp_intuitionistic_status"


def test_qmltp_status_table_uses_logic_and_domain(tmp_path: Path):
    problem = _problem(
        tmp_path,
        """
% Status   :      varying      cumulative   constant
%             D   Non-Theorem  Theorem      Unsolved      v1.1
%             S5  Theorem      Non-Theorem  Theorem       v1.1
qmf(c,conjecture,#box:p).
""",
    )

    status = benchmark_status(problem, logic="D", domain="cumulative")

    assert status is not None
    assert status.label == "Theorem"
    assert status.szs_status == "Theorem"
    assert status.source == "qmltp_status_table"


def test_qmltp_unsolved_keeps_label_without_expected_target(tmp_path: Path):
    problem = _problem(
        tmp_path,
        """
% Status   :      varying      cumulative   constant
%             D   Non-Theorem  Theorem      Unsolved      v1.1
qmf(c,conjecture,#box:p).
""",
    )

    status = benchmark_status(problem, logic="D", domain="constant")

    assert status is not None
    assert status.label == "Unsolved"
    assert status.szs_status is None


def test_status_check_uses_expected_status_over_reference_status():
    assert status_check_passed(
        {
            "expected_status": "Theorem",
            "expected_status_label": "Theorem",
            "native_expected_match": True,
            "status_match": False,
        }
    )
    assert not status_check_passed(
        {
            "expected_status": "Theorem",
            "expected_status_label": "Theorem",
            "native_expected_match": False,
            "status_match": True,
        }
    )


def test_status_check_does_not_fail_unknown_benchmark_label():
    assert status_check_passed(
        {
            "expected_status": None,
            "expected_status_label": "Unsolved",
            "status_match": False,
        }
    )


def _problem(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "problem.p"
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path
