from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Literal, Mapping, Sequence

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.syntax.logic import Domain, Logic
from connections.prover.status import SZSStatus
from connections.prover.prover import ProblemSpec, Prover
from connections.prover.strategy import StrategySchedule
from provers.pycop.settings_codec import LeancopSettingsCodec
from connections.runs import select_problem_paths
from tools.parity.benchmark_status import benchmark_status

ReferenceProver = Literal["leancop21", "ileancop12", "mleancop13"]
ReferenceMode = Literal["raw", "swi-compat"]

REFERENCE_STATUS_TO_SZS = {
    "Theorem": SZSStatus.THEOREM.value,
    "Non-Theorem": SZSStatus.COUNTER_SATISFIABLE.value,
    "Unsatisfiable": SZSStatus.UNSATISFIABLE.value,
    "Satisfiable": SZSStatus.SATISFIABLE.value,
}


@dataclass(frozen=True, slots=True)
class StatusCheckCase:
    name: str
    source: str
    reference: ReferenceProver
    logic: Logic
    domain: Domain = "constant"
    settings: tuple[str, ...] = ()


DEFAULT_STATUS_CASES: tuple[StatusCheckCase, ...] = (
    StatusCheckCase(
        name="classical_tautology",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="leancop21",
        logic="classical",
        settings=("cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="classical_open_atom",
        source="fof(c,conjecture,p).\n",
        reference="leancop21",
        logic="classical",
        settings=("cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="intuitionistic_tautology",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="ileancop12",
        logic="intuitionistic",
        settings=("def", "scut", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="intuitionistic_excluded_middle",
        source="fof(c,conjecture,(p | ~p)).\n",
        reference="ileancop12",
        logic="intuitionistic",
        settings=("def", "scut", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_d_box_implies_diamond",
        source="qmf(c,conjecture,(#box:p => #dia:p)).\n",
        reference="mleancop13",
        logic="D",
        domain="constant",
        settings=("scut", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_d_box_implies_plain",
        source="qmf(c,conjecture,(#box:p => p)).\n",
        reference="mleancop13",
        logic="D",
        domain="constant",
        settings=("scut", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_t_box_implies_plain",
        source="qmf(c,conjecture,(#box:p => p)).\n",
        reference="mleancop13",
        logic="T",
        domain="constant",
        settings=("scut", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_s4_box_implies_box_box",
        source="qmf(c,conjecture,(#box:p => #box:(#box:p))).\n",
        reference="mleancop13",
        logic="S4",
        domain="constant",
        settings=("scut", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_s5_diamond_implies_box_diamond",
        source="qmf(c,conjecture,(#dia:p => #box:(#dia:p))).\n",
        reference="mleancop13",
        logic="S5",
        domain="constant",
        settings=("scut", "cut", "comp(7)"),
    ),
)


def status_check_row(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    swipl: str = "swipl",
    timeout_seconds: float = 10.0,
    reference_mode: ReferenceMode = "swi-compat",
    source_file_dirs: Sequence[str | Path] = (),
) -> dict[str, Any]:
    native_status = native_pycop_status(
        case,
        problem_path=problem_path,
        timeout_seconds=timeout_seconds,
        source_file_dirs=source_file_dirs,
    )
    reference_status = reference_prover_status(
        case,
        problem_path=problem_path,
        swipl=swipl,
        timeout_seconds=timeout_seconds,
        reference_mode=reference_mode,
        source_file_dirs=source_file_dirs,
    )
    expected = benchmark_status(
        problem_path,
        logic=case.logic,
        domain=case.domain,
    )
    expected_status = None if expected is None else expected.szs_status
    return {
        "schema": "connections.status_check_row.v1",
        "name": case.name,
        "reference": case.reference,
        "reference_mode": reference_mode,
        "logic": case.logic,
        "domain": case.domain,
        "settings": list(case.settings),
        "source_file_dirs": [str(Path(path).resolve()) for path in source_file_dirs],
        "expected_status": expected_status,
        "expected_status_label": None if expected is None else expected.label,
        "expected_status_source": None if expected is None else expected.source,
        "native_status": native_status,
        "reference_status": reference_status,
        "native_expected_match": (
            None if expected_status is None else native_status == expected_status
        ),
        "reference_expected_match": (
            None if expected_status is None else reference_status == expected_status
        ),
        "status_match": native_status == reference_status,
    }


def native_pycop_status(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    timeout_seconds: float,
    source_file_dirs: Sequence[str | Path] = (),
) -> str | None:
    strategy = LeancopSettingsCodec.from_tokens(list(case.settings))
    problem = ProblemSpec(
        problem_path,
        logic=case.logic,
        domain=case.domain,
        source_file_dirs=tuple(source_file_dirs),
    )
    result = Prover().run(
        problem,
        schedule=StrategySchedule.single(
            strategy,
            timeout_seconds=timeout_seconds,
        ),
    )
    return None if result.szs_status is None else result.szs_status.value


def reference_prover_status(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    swipl: str,
    timeout_seconds: float,
    reference_mode: ReferenceMode = "swi-compat",
    source_file_dirs: Sequence[str | Path] = (),
) -> str:
    try:
        completed = subprocess.run(
            _reference_command(
                case,
                problem_path=problem_path,
                swipl=swipl,
                reference_mode=reference_mode,
            ),
            check=False,
            capture_output=True,
            env=_reference_env(source_file_dirs),
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return SZSStatus.TIMEOUT.value
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{case.reference} failed for {case.name}: {message}")
    return _parse_reference_status(completed.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check native pycop proof status against benchmark annotations and "
            "record leanCoP-family reference status as telemetry."
        )
    )
    parser.add_argument("--swipl", default="swipl")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-case timeout in seconds for native and reference runs.",
    )
    parser.add_argument(
        "--reference-mode",
        choices=("raw", "swi-compat"),
        default="swi-compat",
        help=(
            "Run references directly or with the parity-local SWI compatibility "
            "adapter."
        ),
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_names",
        default=[],
        help="Run only a named status-check case. May be repeated.",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=[],
        help=(
            "Problem file or directory for corpus status checking. When supplied, "
            "built-in cases are not used."
        ),
    )
    parser.add_argument("--pattern", default="*.p")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--logic",
        default="classical",
        choices=("classical", "intuitionistic", "D", "T", "S4", "S5"),
        help="Logic for --path corpus status checking.",
    )
    parser.add_argument(
        "--domain",
        default="constant",
        choices=("constant", "cumulative", "varying"),
        help="Domain for --path corpus status checking.",
    )
    parser.add_argument(
        "--reference",
        default="leancop21",
        choices=("leancop21", "ileancop12", "mleancop13"),
        help="Reference prover used for status telemetry.",
    )
    parser.add_argument(
        "--settings",
        "--setting",
        action="append",
        dest="settings",
        default=[],
        help="leanCoP setting token for --path corpus status checking. May be repeated.",
    )
    parser.add_argument(
        "--source-dir",
        action="append",
        default=[],
        help=(
            "Directory used to resolve included problem source files. The first "
            "entry is also passed to Prolog references as TPTP."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write JSON rows instead of a text report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows: list[dict[str, Any]] = []
    if args.paths:
        for case, problem_path in _path_cases(args):
            rows.append(
                status_check_row(
                    case,
                    problem_path=problem_path,
                    swipl=args.swipl,
                    timeout_seconds=args.timeout,
                    reference_mode=args.reference_mode,
                    source_file_dirs=tuple(args.source_dir),
                )
            )
    else:
        cases = _selected_cases(args.case_names)
        with tempfile.TemporaryDirectory(prefix="connections-status-check-") as tmp:
            tmp_path = Path(tmp)
            for case in cases:
                problem_path = tmp_path / f"{case.name}.p"
                problem_path.write_text(case.source, encoding="utf-8")
                rows.append(
                    status_check_row(
                        case,
                        problem_path=problem_path,
                        swipl=args.swipl,
                        timeout_seconds=args.timeout,
                        reference_mode=args.reference_mode,
                        source_file_dirs=tuple(args.source_dir),
                    )
                )
    if not args.json:
        for row in rows:
            status = "ok" if status_check_passed(row) else "mismatch"
            if row["expected_status"] is not None:
                target = f"expected={row['expected_status']}"
            elif row["expected_status_label"] is not None:
                target = f"expected_label={row['expected_status_label']}"
            else:
                target = f"reference={row['reference_status']}"
            print(
                f"{status} {row['name']}: "
                f"{target} "
                f"native={row['native_status']}"
            )
    if args.json:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    return 0 if all(status_check_passed(row) for row in rows) else 1


def status_check_passed(row: Mapping[str, Any]) -> bool:
    if row.get("native_status") == SZSStatus.ERROR.value:
        return False
    if row.get("expected_status") is not None:
        return row.get("native_expected_match") is True
    if row.get("expected_status_label") is not None:
        return True
    return row.get("status_match") is True


def _selected_cases(case_names: list[str]) -> tuple[StatusCheckCase, ...]:
    if not case_names:
        return DEFAULT_STATUS_CASES
    selected = set(case_names)
    cases = tuple(case for case in DEFAULT_STATUS_CASES if case.name in selected)
    missing = selected - {case.name for case in cases}
    if missing:
        raise ValueError(f"unknown status-check case(s): {sorted(missing)}")
    return cases


def _path_cases(args: argparse.Namespace) -> tuple[tuple[StatusCheckCase, Path], ...]:
    paths = select_problem_paths(
        args.paths,
        pattern=args.pattern,
        recursive=not args.no_recursive,
        limit=args.limit,
    )
    return tuple(
        (
            StatusCheckCase(
                name=path.name,
                source="",
                reference=args.reference,
                logic=args.logic,
                domain=args.domain,
                settings=tuple(args.settings),
            ),
            path,
        )
        for path in paths
    )


def _reference_command(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    swipl: str,
    reference_mode: ReferenceMode,
) -> list[str]:
    source = _reference_source(case.reference)
    goal = _reference_goal(
        case,
        problem_path=problem_path,
        reference_mode=reference_mode,
    )
    goal = f"set_prolog_flag(encoding,iso_latin_1),{goal}"
    if reference_mode == "swi-compat" and case.reference in {
        "ileancop12",
        "mleancop13",
    }:
        wrapped_goal = (
            f"consult({_prolog_atom(_swi_compatibility_source())}),"
            f"consult({_prolog_atom(source)}),"
            f"{goal}"
        )
        return [swipl, "-q", "-g", wrapped_goal, "-t", "halt"]
    return [swipl, "-q", "-s", str(source), "-g", goal, "-t", "halt"]


def _reference_env(source_file_dirs: Sequence[str | Path]) -> dict[str, str] | None:
    if not source_file_dirs:
        return None
    env = os.environ.copy()
    env["TPTP"] = str(Path(source_file_dirs[0]).resolve())
    return env


def _reference_goal(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    reference_mode: ReferenceMode,
) -> str:
    settings = _prolog_settings(case.settings)
    problem = _prolog_atom(problem_path)
    if case.reference == "leancop21":
        return f"leancop_main({problem},{settings},Result),writeln(Result)"
    if case.reference == "ileancop12":
        if reference_mode == "swi-compat":
            translator = _prolog_atom(
                _reference_dir(case.reference) / "leancop_tptp2.pl"
            )
            return (
                f"consult({translator}),"
                f"compat_ileancop_main({problem},{settings},Result),"
                "writeln(Result)"
            )
        translator = _prolog_atom(_reference_dir(case.reference) / "leancop_tptp2.pl")
        return (
            f"consult({translator}),"
            f"(leancop_tptp2({problem},'',[_],F,Conj)"
            "->Problem=F;(consult("
            f"{problem}),f(Problem),Conj=non_empty)),"
            "(Conj\\=[]->Problem1=Problem;Problem1=(Problem=>false___)),"
            f"(prove2(Problem1,{settings})"
            "->(Conj\\=[]->Result='Theorem';Result='Unsatisfiable')"
            ";(Conj\\=[]->Result='Non-Theorem';Result='Satisfiable')),"
            "nl,writeln(Result)"
        )
    if case.reference == "mleancop13":
        if reference_mode == "swi-compat":
            return (
                f"retractall(logic(_)),assertz(logic({_prolog_logic(case.logic)})),"
                f"retractall(domain(_)),assertz(domain({_prolog_domain(case.domain)})),"
                f"compat_mleancop_main({problem},{settings},Result),"
                "writeln(Result)"
            )
        return (
            f"retractall(logic(_)),assertz(logic({_prolog_logic(case.logic)})),"
            f"retractall(domain(_)),assertz(domain({_prolog_domain(case.domain)})),"
            f"mleancop_main({problem},{settings},Result),writeln(Result)"
        )
    raise ValueError(f"unsupported reference prover: {case.reference!r}")


def _parse_reference_status(output: str) -> str:
    for line in reversed(output.splitlines()):
        status = line.strip().strip("'")
        if status in REFERENCE_STATUS_TO_SZS:
            return REFERENCE_STATUS_TO_SZS[status]
        for reference_status, szs_status in REFERENCE_STATUS_TO_SZS.items():
            if line.rstrip().endswith(f" {reference_status}"):
                return szs_status
    raise RuntimeError(f"could not parse reference status from output: {output!r}")


def _reference_source(reference: ReferenceProver) -> Path:
    directory = _reference_dir(reference)
    if reference == "leancop21":
        return directory / "leancop_main.pl"
    if reference == "ileancop12":
        return directory / "ileancop12.pl"
    if reference == "mleancop13":
        return directory / "mleancop_main.pl"
    raise ValueError(f"unsupported reference prover: {reference!r}")


def _reference_dir(reference: ReferenceProver) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "tools" / "parity" / "reference_provers" / "prolog" / reference


def _prolog_atom(value: str | Path) -> str:
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _prolog_settings(settings: tuple[str, ...]) -> str:
    return "[" + ",".join(settings) + "]"


def _swi_compatibility_source() -> Path:
    return Path(__file__).resolve().parent / "prolog" / "swi_compat.pl"


def _prolog_logic(logic: Logic) -> str:
    return "d" if logic == "D" else logic.lower()


def _prolog_domain(domain: Domain) -> str:
    return {
        "constant": "const",
        "cumulative": "cumul",
        "varying": "vary",
    }[domain]


__all__ = [
    "DEFAULT_STATUS_CASES",
    "ReferenceMode",
    "ReferenceProver",
    "StatusCheckCase",
    "build_parser",
    "main",
    "native_pycop_status",
    "reference_prover_status",
    "status_check_row",
    "status_check_passed",
]


if __name__ == "__main__":
    raise SystemExit(main())
