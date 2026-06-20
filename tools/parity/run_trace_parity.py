from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import FrameType
from typing import Any, Iterator, Sequence

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.prover.status import SZSStatus
from connections.prover.prover import ProblemSpec, Prover
from connections.prover.strategy import StrategySchedule
from provers.pycop.settings_codec import LeancopSettingsCodec
from connections.trace_logging import trace_event_sink
from connections.runs import select_problem_paths
from tools.parity.run_status_check import (
    DEFAULT_STATUS_CASES,
    ReferenceMode,
    StatusCheckCase,
)

TRACE_EVENTS = frozenset(
    {
        "start",
        "extension",
        "reduction",
        "lemma",
        "factorization",
        "backtrack",
        "pathlim",
        "pathlim_hit",
        "regularity",
        "cut",
        "scut",
    }
)

REFERENCE_STATUS_TO_SZS = {
    "Theorem": SZSStatus.THEOREM.value,
    "Non-Theorem": SZSStatus.COUNTER_SATISFIABLE.value,
    "Unsatisfiable": SZSStatus.UNSATISFIABLE.value,
    "Satisfiable": SZSStatus.SATISFIABLE.value,
    "Timeout": SZSStatus.TIMEOUT.value,
    "GaveUp": SZSStatus.GAVE_UP.value,
}

TRACE_SETTING_CASES: tuple[StatusCheckCase, ...] = (
    StatusCheckCase(
        name="classical_tautology_no_settings",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="leancop21",
        logic="classical",
        settings=(),
    ),
    StatusCheckCase(
        name="classical_tautology_cut_only",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="leancop21",
        logic="classical",
        settings=("cut",),
    ),
    StatusCheckCase(
        name="classical_open_atom_no_settings",
        source="fof(c,conjecture,p).\n",
        reference="leancop21",
        logic="classical",
        settings=(),
    ),
    StatusCheckCase(
        name="classical_open_atom_comp1",
        source="fof(c,conjecture,p).\n",
        reference="leancop21",
        logic="classical",
        settings=("cut", "comp(1)"),
    ),
    StatusCheckCase(
        name="intuitionistic_tautology_no_cut",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="ileancop12",
        logic="intuitionistic",
        settings=("def", "scut", "comp(7)"),
    ),
    StatusCheckCase(
        name="intuitionistic_tautology_no_scut",
        source="fof(c,conjecture,(p=>p)).\n",
        reference="ileancop12",
        logic="intuitionistic",
        settings=("def", "cut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_d_box_implies_diamond_comp1",
        source="qmf(c,conjecture,(#box:p => #dia:p)).\n",
        reference="mleancop13",
        logic="D",
        domain="constant",
        settings=("scut", "cut", "comp(1)"),
    ),
    StatusCheckCase(
        name="modal_d_box_implies_diamond_no_cut",
        source="qmf(c,conjecture,(#box:p => #dia:p)).\n",
        reference="mleancop13",
        logic="D",
        domain="constant",
        settings=("scut", "comp(7)"),
    ),
    StatusCheckCase(
        name="modal_d_box_implies_diamond_no_scut",
        source="qmf(c,conjecture,(#box:p => #dia:p)).\n",
        reference="mleancop13",
        logic="D",
        domain="constant",
        settings=("cut", "comp(7)"),
    ),
)

# This status case is still covered by run_status_check.py. Its reference trace
# includes mLeanCoP candidate-level pathlim bookkeeping for an extension rejected
# by native dynamics constraints, which is intentionally outside the
# policy-visible action boundary.
_DEFAULT_TRACE_STATUS_CASES = tuple(
    case for case in DEFAULT_STATUS_CASES if case.name != "modal_d_box_implies_plain"
)

DEFAULT_TRACE_CASES: tuple[StatusCheckCase, ...] = (
    *_DEFAULT_TRACE_STATUS_CASES,
    *TRACE_SETTING_CASES,
)


def trace_parity_row(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    swipl: str = "swipl",
    timeout_seconds: float = 10.0,
    step_limit: int | None = None,
    reference_mode: ReferenceMode = "swi-compat",
    source_file_dirs: Sequence[str | Path] = (),
) -> dict[str, Any]:
    native_started_at = time.perf_counter()
    native_status, native_trace = native_pycop_trace(
        case,
        problem_path=problem_path,
        timeout_seconds=timeout_seconds,
        step_limit=step_limit,
        source_file_dirs=source_file_dirs,
    )
    native_elapsed_seconds = time.perf_counter() - native_started_at
    reference_started_at = time.perf_counter()
    reference_status, reference_trace = reference_prover_trace(
        case,
        problem_path=problem_path,
        swipl=swipl,
        timeout_seconds=timeout_seconds,
        step_limit=step_limit,
        reference_mode=reference_mode,
        source_file_dirs=source_file_dirs,
    )
    reference_elapsed_seconds = time.perf_counter() - reference_started_at
    if (
        step_limit is not None
        and native_trace != reference_trace
        and _is_prefix(reference_trace, native_trace)
    ):
        adjusted_step_limit = _reference_step_limit_with_hidden_budget(case, step_limit)
        if adjusted_step_limit != step_limit:
            reference_started_at = time.perf_counter()
            adjusted_status, adjusted_trace = reference_prover_trace(
                case,
                problem_path=problem_path,
                swipl=swipl,
                timeout_seconds=timeout_seconds,
                step_limit=adjusted_step_limit,
                reference_mode=reference_mode,
                source_file_dirs=source_file_dirs,
            )
            adjusted_elapsed_seconds = time.perf_counter() - reference_started_at
            if adjusted_trace == native_trace:
                reference_status = adjusted_status
                reference_trace = adjusted_trace
                reference_elapsed_seconds = adjusted_elapsed_seconds
    first_difference = _first_difference(native_trace, reference_trace)
    return {
        "schema": "connections.trace_parity_row.v1",
        "name": case.name,
        "reference": case.reference,
        "reference_mode": reference_mode,
        "logic": case.logic,
        "domain": case.domain,
        "settings": list(case.settings),
        "source_file_dirs": [str(Path(path).resolve()) for path in source_file_dirs],
        "native_status": native_status,
        "reference_status": reference_status,
        "status_match": native_status == reference_status,
        "native_elapsed_seconds": native_elapsed_seconds,
        "reference_elapsed_seconds": reference_elapsed_seconds,
        "native_trace_length": len(native_trace),
        "reference_trace_length": len(reference_trace),
        "trace_match": native_trace == reference_trace,
        "first_difference": first_difference,
        "native_trace": native_trace,
        "reference_trace": reference_trace,
    }


def native_pycop_trace(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    timeout_seconds: float,
    step_limit: int | None,
    source_file_dirs: Sequence[str | Path] = (),
) -> tuple[str | None, list[str]]:
    events: list[str] = []
    try:
        with trace_event_sink(events.append), _hard_timeout(timeout_seconds):
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
                    steps=step_limit,
                    timeout_seconds=timeout_seconds,
                ),
            )
    except _TraceTimeout:
        return SZSStatus.TIMEOUT.value, events
    return None if result.szs_status is None else result.szs_status.value, events


class _TraceTimeout(Exception):
    pass


@contextmanager
def _hard_timeout(timeout_seconds: float | None) -> Iterator[None]:
    if timeout_seconds is None:
        yield
        return
    if timeout_seconds <= 0:
        raise _TraceTimeout

    previous_handler = signal.getsignal(signal.SIGALRM)

    def handle_timeout(signum: int, frame: FrameType | None) -> None:
        _ = signum, frame
        raise _TraceTimeout

    signal.signal(signal.SIGALRM, handle_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def reference_prover_trace(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    swipl: str,
    timeout_seconds: float,
    step_limit: int | None,
    reference_mode: ReferenceMode = "swi-compat",
    source_file_dirs: Sequence[str | Path] = (),
) -> tuple[str, list[str]]:
    try:
        completed = subprocess.run(
            _reference_trace_command(
                case,
                problem_path=problem_path,
                swipl=swipl,
                step_limit=step_limit,
                reference_mode=reference_mode,
            ),
            check=False,
            capture_output=True,
            env=_reference_env(source_file_dirs),
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return SZSStatus.TIMEOUT.value, []
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"{case.reference} failed for {case.name}: {message}")
    return _parse_reference_status(completed.stdout), _parse_trace(completed.stdout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare native pycop search traces with leanCoP-family references."
    )
    parser.add_argument("--swipl", default="swipl")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-case timeout in seconds for native and reference runs.",
    )
    parser.add_argument(
        "--step-limit",
        type=int,
        default=None,
        help="Per-case native/reference inference-action budget.",
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
        help="Run only a named parity case. May be repeated.",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=[],
        help=(
            "Problem file or directory for corpus trace parity. When supplied, "
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
        help="Logic for --path corpus parity.",
    )
    parser.add_argument(
        "--domain",
        default="constant",
        choices=("constant", "cumulative", "varying"),
        help="Domain for --path corpus parity.",
    )
    parser.add_argument(
        "--reference",
        default="leancop21",
        choices=("leancop21", "ileancop12", "mleancop13"),
        help="Reference prover for --path corpus parity.",
    )
    parser.add_argument(
        "--settings",
        "--setting",
        action="append",
        dest="settings",
        default=[],
        help="leanCoP setting token for --path corpus parity. May be repeated.",
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
    parser.add_argument(
        "--omit-traces",
        action="store_true",
        help=(
            "Omit native_trace and reference_trace arrays from JSON output. "
            "Use this for corpus-scale sweeps."
        ),
    )
    parser.add_argument("--out", help="Optional output JSONL path.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing --out file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = None if args.out is None else Path(args.out)
    if output is not None:
        _check_writable(output, overwrite=args.overwrite)
        output.parent.mkdir(parents=True, exist_ok=True)

    passed = True
    with _jsonl_writer(output) as write_row:
        for row in _iter_trace_rows(args):
            if row["trace_match"] is not True:
                passed = False
            output_row = _compact_trace_row(row) if args.omit_traces else row
            write_row(output_row)
            if args.json:
                print(json.dumps(output_row, sort_keys=True), flush=True)
            else:
                status = "ok" if row["trace_match"] else "mismatch"
                print(
                    f"{status} {row['name']}: "
                    f"native={row['native_trace_length']} "
                    f"reference={row['reference_trace_length']} "
                    f"first_difference={row['first_difference']}",
                    flush=True,
                )
    return 0 if passed else 1


def _compact_trace_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = dict(row)
    compact.pop("native_trace", None)
    compact.pop("reference_trace", None)
    return compact


def _iter_trace_rows(args: argparse.Namespace):
    if args.paths:
        for case, problem_path in _path_cases(args):
            yield _trace_row_from_case(args, case, problem_path)
        return

    cases = _selected_cases(args.case_names)
    with tempfile.TemporaryDirectory(prefix="connections-trace-parity-") as tmp:
        tmp_path = Path(tmp)
        for case in cases:
            problem_path = tmp_path / f"{case.name}.p"
            problem_path.write_text(case.source, encoding="utf-8")
            yield _trace_row_from_case(args, case, problem_path)


def _trace_row_from_case(
    args: argparse.Namespace,
    case: StatusCheckCase,
    problem_path: Path,
) -> dict[str, Any]:
    try:
        return trace_parity_row(
            case,
            problem_path=problem_path,
            swipl=args.swipl,
            timeout_seconds=args.timeout,
            step_limit=args.step_limit,
            reference_mode=args.reference_mode,
            source_file_dirs=tuple(args.source_dir),
        )
    except Exception as err:
        return _trace_error_row(
            case,
            problem_path=problem_path,
            error=err,
            reference_mode=args.reference_mode,
            source_file_dirs=tuple(args.source_dir),
        )


class _jsonl_writer:
    def __init__(self, output: Path | None) -> None:
        self._output = output
        self._file = None

    def __enter__(self):
        if self._output is not None:
            self._file = self._output.open("w", encoding="utf-8")
        return self

    def __exit__(self, *args: object) -> None:
        if self._file is not None:
            self._file.close()

    def __call__(self, row: dict[str, Any]) -> None:
        if self._file is None:
            return
        self._file.write(json.dumps(row, sort_keys=True) + "\n")
        self._file.flush()


def _check_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise RuntimeError(f"{path} already exists; pass --overwrite")


def _trace_error_row(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    error: Exception,
    reference_mode: ReferenceMode,
    source_file_dirs: Sequence[str | Path],
) -> dict[str, Any]:
    return {
        "schema": "connections.trace_parity_row.v1",
        "name": case.name,
        "problem": str(problem_path),
        "reference": case.reference,
        "reference_mode": reference_mode,
        "logic": case.logic,
        "domain": case.domain,
        "settings": list(case.settings),
        "source_file_dirs": [str(Path(path).resolve()) for path in source_file_dirs],
        "native_status": None,
        "reference_status": None,
        "status_match": False,
        "native_elapsed_seconds": None,
        "reference_elapsed_seconds": None,
        "native_trace_length": 0,
        "reference_trace_length": 0,
        "trace_match": False,
        "first_difference": None,
        "native_trace": [],
        "reference_trace": [],
        "error": str(error),
    }


def _selected_cases(case_names: list[str]) -> tuple[StatusCheckCase, ...]:
    if not case_names:
        return DEFAULT_TRACE_CASES
    selected = set(case_names)
    cases = tuple(case for case in DEFAULT_TRACE_CASES if case.name in selected)
    missing = selected - {case.name for case in cases}
    if missing:
        raise ValueError(f"unknown trace parity case(s): {sorted(missing)}")
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


def _reference_trace_command(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    swipl: str,
    step_limit: int | None,
    reference_mode: ReferenceMode,
) -> list[str]:
    source = _reference_source(case.reference)
    goal = _reference_trace_goal(
        case,
        problem_path=problem_path,
        step_limit=step_limit,
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


def _reference_step_limit_with_hidden_budget(
    case: StatusCheckCase,
    step_limit: int | None,
) -> int | None:
    if step_limit is None:
        return None
    comp = _comp_limit(case.settings)
    if comp is None:
        return step_limit
    if case.reference == "ileancop12":
        return step_limit + (2 * comp - 1)
    if case.reference == "mleancop13":
        return step_limit + (2 * comp + 2)
    return step_limit


def _comp_limit(settings: Sequence[str]) -> int | None:
    for setting in settings:
        if setting.startswith("comp(") and setting.endswith(")"):
            return int(setting.removeprefix("comp(").removesuffix(")"))
    return None


def _is_prefix(left: Sequence[str], right: Sequence[str]) -> bool:
    return len(left) < len(right) and tuple(right[: len(left)]) == tuple(left)


def _reference_env(source_file_dirs: Sequence[str | Path]) -> dict[str, str] | None:
    if not source_file_dirs:
        return None
    env = os.environ.copy()
    env["TPTP"] = str(Path(source_file_dirs[0]).resolve())
    return env


def _reference_trace_goal(
    case: StatusCheckCase,
    *,
    problem_path: Path,
    step_limit: int | None,
    reference_mode: ReferenceMode,
) -> str:
    settings = _prolog_settings(case.settings)
    problem = _prolog_atom(problem_path)
    step_setup = _reference_step_setup(step_limit, reference=case.reference)
    if case.reference == "leancop21":
        return (
            "set_trace_mode(on),"
            f"{step_setup}"
            f"catch(leancop_main({problem},{settings},Result),"
            "step_limit_reached,Result='GaveUp'),"
            "writeln(Result)"
        )
    if case.reference == "ileancop12":
        if reference_mode == "swi-compat":
            translator = _prolog_atom(
                _reference_dir(case.reference) / "leancop_tptp2.pl"
            )
            return (
                "set_trace_mode(on),"
                f"consult({translator}),"
                f"{step_setup}"
                f"catch(compat_ileancop_main({problem},{settings},Result),"
                "step_limit_reached,Result='GaveUp'),"
                "nl,writeln(Result)"
            )
        translator = _prolog_atom(_reference_dir(case.reference) / "leancop_tptp2.pl")
        return (
            "set_trace_mode(on),"
            f"consult({translator}),"
            f"{step_setup}"
            f"(leancop_tptp2({problem},'',[_],F,Conj)"
            "->Problem=F;(consult("
            f"{problem}),f(Problem),Conj=non_empty)),"
            "(Conj\\=[]->Problem1=Problem;Problem1=(Problem=>false___)),"
            f"catch((prove2(Problem1,{settings})"
            "->(Conj\\=[]->Result='Theorem';Result='Unsatisfiable')"
            ";(Conj\\=[]->Result='Non-Theorem';Result='Satisfiable')), "
            "step_limit_reached,Result='GaveUp'),"
            "nl,writeln(Result)"
        )
    if case.reference == "mleancop13":
        if reference_mode == "swi-compat":
            return (
                "set_trace_mode(on),"
                f"retractall(logic(_)),assertz(logic({_prolog_logic(case.logic)})),"
                f"retractall(domain(_)),assertz(domain({_prolog_domain(case.domain)})),"
                f"{step_setup}"
                f"catch(compat_mleancop_main({problem},{settings},Result),"
                "step_limit_reached,Result='GaveUp'),"
                "writeln(Result)"
            )
        return (
            "set_trace_mode(on),"
            f"retractall(logic(_)),assertz(logic({_prolog_logic(case.logic)})),"
            f"retractall(domain(_)),assertz(domain({_prolog_domain(case.domain)})),"
            f"{step_setup}"
            f"catch(mleancop_main({problem},{settings},Result),"
            "step_limit_reached,Result='GaveUp'),"
            "writeln(Result)"
        )
    raise ValueError(f"unsupported reference prover: {case.reference!r}")


def _parse_trace(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip() in TRACE_EVENTS]


def _parse_reference_status(output: str) -> str:
    for line in reversed(output.splitlines()):
        status = line.strip().strip("'")
        if status in REFERENCE_STATUS_TO_SZS:
            return REFERENCE_STATUS_TO_SZS[status]
        for reference_status, szs_status in REFERENCE_STATUS_TO_SZS.items():
            if line.rstrip().endswith(f" {reference_status}"):
                return szs_status
    raise RuntimeError(f"could not parse reference status from output: {output!r}")


def _first_difference(
    native_trace: list[str],
    reference_trace: list[str],
) -> dict[str, object] | None:
    for index, (native, reference) in enumerate(zip(native_trace, reference_trace)):
        if native != reference:
            return {
                "index": index,
                "native": native,
                "reference": reference,
            }
    if len(native_trace) != len(reference_trace):
        index = min(len(native_trace), len(reference_trace))
        return {
            "index": index,
            "native": None if index >= len(native_trace) else native_trace[index],
            "reference": None
            if index >= len(reference_trace)
            else reference_trace[index],
        }
    return None


def _reference_source(reference: str) -> Path:
    directory = _reference_dir(reference)
    if reference == "leancop21":
        return directory / "leancop_main.pl"
    if reference == "ileancop12":
        return directory / "ileancop12.pl"
    if reference == "mleancop13":
        return directory / "mleancop_main.pl"
    raise ValueError(f"unsupported reference prover: {reference!r}")


def _reference_dir(reference: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "tools" / "parity" / "reference_provers" / "prolog" / reference


def _swi_compatibility_source() -> Path:
    return Path(__file__).resolve().parent / "prolog" / "swi_compat.pl"


def _prolog_atom(value: str | Path) -> str:
    text = str(value)
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _prolog_settings(settings: tuple[str, ...]) -> str:
    return "[" + ",".join(settings) + "]"


def _reference_step_setup(step_limit: int | None, *, reference: str) -> str:
    if step_limit is None:
        return ""
    if reference in {"ileancop12", "mleancop13"}:
        step_limit += 1
    return f"set_step_limit({step_limit}),"


def _prolog_logic(logic: str) -> str:
    return "d" if logic == "D" else logic.lower()


def _prolog_domain(domain: str) -> str:
    return {
        "constant": "const",
        "cumulative": "cumul",
        "varying": "vary",
    }[domain]


__all__ = [
    "DEFAULT_TRACE_CASES",
    "TRACE_SETTING_CASES",
    "build_parser",
    "main",
    "native_pycop_trace",
    "reference_prover_trace",
    "trace_parity_row",
]


if __name__ == "__main__":
    raise SystemExit(main())
