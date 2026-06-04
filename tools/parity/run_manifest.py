from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Literal, cast

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.core.logic import Domain, Logic
from tools.corpus.selection import select_problem_paths
from tools.parity.run_matrix_parity import MatrixParityCase, matrix_parity_row
from tools.parity.run_status_check import (
    ReferenceMode,
    ReferenceProver,
    StatusCheckCase,
    status_check_row,
)
from tools.parity.run_trace_parity import trace_parity_row

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = Path(__file__).with_name("manifests") / "full-0.1.json"

SweepKind = Literal["matrix", "status_check", "trace"]


@dataclass(frozen=True, slots=True)
class ParitySweep:
    name: str
    kind: SweepKind
    paths: tuple[Path, ...]
    source_dirs: tuple[Path, ...]
    reference: ReferenceProver
    logic: Logic
    domain: Domain
    settings: tuple[str, ...]
    pattern: str = "*.p"
    recursive: bool = True
    limit: int | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run manifest-defined status checks and parity sweeps."
    )
    parser.add_argument(
        "--manifest",
        default=str(_DEFAULT_MANIFEST),
        help="Parity manifest JSON file. Defaults to tools/parity/manifests/full-0.1.json.",
    )
    parser.add_argument("--swipl", default="swipl")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-problem timeout in seconds for native and reference runs.",
    )
    parser.add_argument(
        "--reference-mode",
        choices=("raw", "swi-compat"),
        default="swi-compat",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only a named sweep. May be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override each selected sweep limit. Use 0 to validate manifest loading only.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip this many selected problem paths from each selected sweep.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Emit skipped rows for missing benchmark roots instead of failing.",
    )
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write one JSON row per problem plus one summary row per sweep.",
    )
    parser.add_argument(
        "--out",
        help="Optional output JSONL path. Writes all problem and sweep summary rows.",
    )
    summary_group = parser.add_mutually_exclusive_group()
    summary_group.add_argument(
        "--summary-out",
        metavar="PATH",
        help="Optional run summary JSON path. Defaults to OUT with .summary.json suffix.",
    )
    summary_group.add_argument(
        "--no-summary",
        action="store_true",
        help="Do not write a run summary JSON sidecar.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing --out or --summary-out files.",
    )
    parser.add_argument(
        "--include-matrices",
        action="store_true",
        help="Include full serialized matrices in matrix sweep rows.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sweeps = _load_manifest(Path(args.manifest), only=tuple(args.only))
    output = None if args.out is None else Path(args.out)
    summary_output = _summary_output_path(output, args)
    if output is not None:
        _check_writable(output, overwrite=args.overwrite)
        output.parent.mkdir(parents=True, exist_ok=True)
    if summary_output is not None:
        if output is not None and summary_output == output:
            raise ValueError("--summary-out must differ from --out")
        _check_writable(summary_output, overwrite=args.overwrite)
        summary_output.parent.mkdir(parents=True, exist_ok=True)

    passed = True
    summaries: list[dict[str, Any]] = []
    manifest_path = Path(args.manifest)
    with _optional_jsonl_writer(output) as write_row:
        for sweep in sweeps:
            for row in _run_sweep(
                sweep,
                swipl=args.swipl,
                timeout_seconds=args.timeout,
                reference_mode=args.reference_mode,
                limit_override=args.limit,
                offset=args.offset,
                allow_missing=args.allow_missing,
                include_matrices=args.include_matrices,
            ):
                if row["schema"] == "connections.parity_manifest_summary.v1":
                    summaries.append(row)
                elif _row_failed(row):
                    passed = False
                write_row(row)
                if args.json:
                    print(json.dumps(row, sort_keys=True), flush=True)
                elif row["schema"] != "connections.parity_manifest_row.v1":
                    print(
                        f"{row['status']} {row['sweep']}: rows={row['rows']} "
                        f"failures={row['failures']} classified={row['classified']}",
                        flush=True,
                    )
                if args.fail_fast and _row_failed(row):
                    break
            else:
                continue
            break
    if summary_output is not None:
        summary_output.write_text(
            json.dumps(
                _run_summary(
                    summaries,
                    manifest=manifest_path,
                    output=output,
                    summary_output=summary_output,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if passed else 1


def _load_manifest(path: Path, *, only: tuple[str, ...]) -> tuple[ParitySweep, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("parity manifest must be a JSON object")
    root = cast(Mapping[str, object], data)
    raw_sweeps = root.get("sweeps")
    if not isinstance(raw_sweeps, list):
        raise ValueError("parity manifest must contain a sweeps list")

    selected = set(only)
    sweeps_list: list[ParitySweep] = []
    for raw in raw_sweeps:
        if not isinstance(raw, Mapping):
            raise ValueError("parity manifest sweep entries must be JSON objects")
        raw_mapping = cast(Mapping[str, object], raw)
        if selected and str(raw_mapping.get("name")) not in selected:
            continue
        sweeps_list.append(_sweep_from_json(raw_mapping))
    sweeps = tuple(sweeps_list)
    if selected:
        missing = selected - {sweep.name for sweep in sweeps}
        if missing:
            raise ValueError(f"unknown sweep(s): {sorted(missing)}")
    return sweeps


def _sweep_from_json(raw: Mapping[str, object]) -> ParitySweep:
    def text(name: str, default: str | None = None) -> str:
        value = raw.get(name, default)
        if not isinstance(value, str):
            raise ValueError(f"sweep field {name!r} must be a string")
        return value

    def optional_int(name: str) -> int | None:
        value = raw.get(name)
        if value is None:
            return None
        if not isinstance(value, int):
            raise ValueError(f"sweep field {name!r} must be an integer")
        return value

    def string_list(name: str) -> tuple[str, ...]:
        value = raw.get(name, ())
        if not isinstance(value, list):
            raise ValueError(f"sweep field {name!r} must be a string list")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"sweep field {name!r} must be a string list")
            items.append(item)
        return tuple(items)

    paths = _paths_field(raw)
    kind = cast(SweepKind, text("kind", "status_check"))
    if kind not in {"matrix", "status_check", "trace"}:
        raise ValueError(f"unsupported sweep kind: {kind!r}")
    return ParitySweep(
        name=text("name"),
        kind=kind,
        paths=paths,
        source_dirs=tuple(_resolve_path(path) for path in string_list("source_dirs")),
        reference=cast(ReferenceProver, text("reference")),
        logic=cast(Logic, text("logic", "classical")),
        domain=cast(Domain, text("domain", "constant")),
        settings=string_list("settings"),
        pattern=text("pattern", "*.p"),
        recursive=_bool_field(raw, "recursive", default=True),
        limit=optional_int("limit"),
    )


def _paths_field(raw: Mapping[str, object]) -> tuple[Path, ...]:
    if "paths" in raw:
        value = raw["paths"]
        if not isinstance(value, list):
            raise ValueError("sweep field 'paths' must be a string list")
        paths: list[Path] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("sweep field 'paths' must be a string list")
            paths.append(_resolve_path(item))
        return tuple(paths)
    value = raw.get("path")
    if not isinstance(value, str):
        raise ValueError("sweep must contain 'path' or 'paths'")
    return (_resolve_path(value),)


def _bool_field(raw: Mapping[str, object], name: str, *, default: bool) -> bool:
    value = raw.get(name, default)
    if not isinstance(value, bool):
        raise ValueError(f"sweep field {name!r} must be a boolean")
    return value


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (_ROOT / path).resolve()


def _run_sweep(
    sweep: ParitySweep,
    *,
    swipl: str,
    timeout_seconds: float,
    reference_mode: ReferenceMode,
    limit_override: int | None,
    offset: int,
    allow_missing: bool,
    include_matrices: bool,
):
    limit = sweep.limit if limit_override is None else limit_override
    try:
        problem_paths = select_problem_paths(
            sweep.paths,
            pattern=sweep.pattern,
            recursive=sweep.recursive,
            limit=limit,
            offset=offset,
        )
    except FileNotFoundError as err:
        if not allow_missing:
            raise
        yield _skipped_summary(sweep, reason=f"missing root: {err}")
        return

    rows = 0
    failures = 0
    classified = 0
    native_timeouts = 0
    reference_timeouts = 0
    status_divergences = 0
    expected_status_rows = 0
    unlabeled_status_rows = 0
    native_expected_failures = 0
    for problem_path in problem_paths:
        row = _problem_row(
            sweep,
            problem_path=problem_path,
            swipl=swipl,
            timeout_seconds=timeout_seconds,
            reference_mode=reference_mode,
            include_matrices=include_matrices,
        )
        rows += 1
        if _row_classified(row):
            classified += 1
        if _row_failed(row):
            failures += 1
        if row.get("native_status") == "Timeout":
            native_timeouts += 1
        if row.get("reference_status") == "Timeout":
            reference_timeouts += 1
        if row.get("status_match") is False:
            status_divergences += 1
        if row.get("expected_status") is not None:
            expected_status_rows += 1
            if row.get("native_expected_match") is not True:
                native_expected_failures += 1
        elif row.get("expected_status_label") is not None:
            unlabeled_status_rows += 1
        yield row
    yield {
        "schema": "connections.parity_manifest_summary.v1",
        "sweep": sweep.name,
        "kind": sweep.kind,
        "status": "ok" if failures == 0 else "failed",
        "rows": rows,
        "failures": failures,
        "classified": classified,
        "native_timeouts": native_timeouts,
        "reference_timeouts": reference_timeouts,
        "status_divergences": status_divergences,
        "expected_status_rows": expected_status_rows,
        "unlabeled_status_rows": unlabeled_status_rows,
        "native_expected_failures": native_expected_failures,
        "paths": [str(path) for path in sweep.paths],
        "source_file_dirs": [str(path) for path in sweep.source_dirs],
    }


def _problem_row(
    sweep: ParitySweep,
    *,
    problem_path: Path,
    swipl: str,
    timeout_seconds: float,
    reference_mode: ReferenceMode,
    include_matrices: bool,
) -> dict[str, Any]:
    case = StatusCheckCase(
        name=problem_path.name,
        source="",
        reference=sweep.reference,
        logic=sweep.logic,
        domain=sweep.domain,
        settings=sweep.settings,
    )
    try:
        if sweep.kind == "matrix":
            row = matrix_parity_row(
                MatrixParityCase(
                    name=problem_path.name,
                    source="",
                    reference=sweep.reference,
                    logic=sweep.logic,
                    domain=sweep.domain,
                    settings=sweep.settings,
                ),
                problem_path=problem_path,
                swipl=swipl,
                timeout_seconds=timeout_seconds,
                source_file_dirs=sweep.source_dirs,
                include_matrices=include_matrices,
            )
        elif sweep.kind == "status_check":
            row = status_check_row(
                case,
                problem_path=problem_path,
                swipl=swipl,
                timeout_seconds=timeout_seconds,
                reference_mode=reference_mode,
                source_file_dirs=sweep.source_dirs,
            )
        elif sweep.kind == "trace":
            row = trace_parity_row(
                case,
                problem_path=problem_path,
                swipl=swipl,
                timeout_seconds=timeout_seconds,
                reference_mode=reference_mode,
                source_file_dirs=sweep.source_dirs,
            )
        else:
            raise AssertionError(f"unsupported sweep kind: {sweep.kind}")
    except Exception as err:
        return {
            "schema": "connections.parity_manifest_row.v1",
            "sweep": sweep.name,
            "kind": sweep.kind,
            "problem": str(problem_path),
            "status": "error",
            "error": str(err),
            "status_match": False,
            "trace_match": False if sweep.kind == "trace" else None,
            "repro_commands": _repro_commands(
                sweep,
                problem_path=problem_path,
                timeout_seconds=timeout_seconds,
                reference_mode=reference_mode,
                swipl=swipl,
                include_matrices=include_matrices,
            ),
        }
    row = dict(row)
    row["schema"] = "connections.parity_manifest_row.v1"
    row["sweep"] = sweep.name
    row["kind"] = sweep.kind
    row["problem"] = str(problem_path)
    classification = _row_classification(row)
    if classification is not None:
        row["status"] = _classified_status(classification)
        row["classification"] = classification
    else:
        row["status"] = "ok" if not _row_failed(row) else "mismatch"
    if row["status"] != "ok":
        row["repro_commands"] = _repro_commands(
            sweep,
            problem_path=problem_path,
            timeout_seconds=timeout_seconds,
            reference_mode=reference_mode,
            swipl=swipl,
            include_matrices=include_matrices,
        )
    return row


def _skipped_summary(sweep: ParitySweep, *, reason: str) -> dict[str, Any]:
    return {
        "schema": "connections.parity_manifest_summary.v1",
        "sweep": sweep.name,
        "kind": sweep.kind,
        "status": "skipped",
        "rows": 0,
        "failures": 0,
        "classified": 0,
        "native_timeouts": 0,
        "reference_timeouts": 0,
        "status_divergences": 0,
        "expected_status_rows": 0,
        "unlabeled_status_rows": 0,
        "native_expected_failures": 0,
        "paths": [str(path) for path in sweep.paths],
        "source_file_dirs": [str(path) for path in sweep.source_dirs],
        "reason": reason,
    }


def _row_classified(row: Mapping[str, Any]) -> bool:
    return _row_classification(row) is not None


def _classified_status(classification: str) -> str:
    if classification == "native_reference_timed_out_against_expected":
        return "shared_timeout"
    if classification == "native_reference_matched_unexpected_status":
        return "reference_benchmark_disagreement"
    if classification.endswith("_timed_out"):
        return "reference_timeout"
    return "status_divergence"


def _row_classification(row: Mapping[str, Any]) -> str | None:
    if (
        row.get("expected_status") is not None
        and row.get("native_status") == "Timeout"
        and row.get("reference_status") == "Timeout"
    ):
        return "native_reference_timed_out_against_expected"
    if (
        row.get("expected_status") is not None
        and row.get("native_expected_match") is not True
        and row.get("native_status") == row.get("reference_status")
        and row.get("native_status") not in {None, "Timeout", "Error"}
    ):
        return "native_reference_matched_unexpected_status"
    if (
        row.get("reference_status") == "Timeout"
        and row.get("native_status") not in {None, "Timeout", "Error"}
    ):
        if row.get("expected_status") is not None:
            if row.get("native_expected_match") is not True:
                return None
            return "native_matched_expected_reference_timed_out"
        return "native_answered_reference_timed_out"
    return (
        "native_reference_status_divergence_without_ground_truth"
        if (
            row.get("expected_status_label") is not None
            and row.get("expected_status") is None
            and row.get("status_match") is False
        )
        else None
    )


def _row_failed(row: Mapping[str, Any]) -> bool:
    if row.get("status") == "error":
        return True
    if row.get("native_status") == "Error":
        return True
    if "matrix_match" in row:
        return row.get("matrix_match") is False
    if "trace_match" in row and row.get("trace_match") is not None:
        return row.get("trace_match") is not True
    if _row_classified(row):
        return False
    if "expected_status" in row:
        if row.get("expected_status") is not None:
            return row.get("native_expected_match") is not True
        if row.get("expected_status_label") is not None:
            return False
    if "status_match" in row:
        return row.get("status_match") is not True
    return False


def _repro_commands(
    sweep: ParitySweep,
    *,
    problem_path: Path,
    timeout_seconds: float,
    reference_mode: ReferenceMode,
    swipl: str,
    include_matrices: bool,
) -> dict[str, list[str]]:
    return {
        "matrix_parity": _parity_command(
            "matrix",
            sweep,
            problem_path=problem_path,
            timeout_seconds=timeout_seconds,
            reference_mode=reference_mode,
            swipl=swipl,
            include_matrices=include_matrices,
        ),
        "status_check": _parity_command(
            "status_check",
            sweep,
            problem_path=problem_path,
            timeout_seconds=timeout_seconds,
            reference_mode=reference_mode,
            swipl=swipl,
            include_matrices=include_matrices,
        ),
        "trace_parity": _parity_command(
            "trace",
            sweep,
            problem_path=problem_path,
            timeout_seconds=timeout_seconds,
            reference_mode=reference_mode,
            swipl=swipl,
            include_matrices=include_matrices,
        ),
        "diagnose_search": _diagnose_command(
            sweep,
            problem_path=problem_path,
            timeout_seconds=timeout_seconds,
        ),
    }


def _parity_command(
    kind: SweepKind,
    sweep: ParitySweep,
    *,
    problem_path: Path,
    timeout_seconds: float,
    reference_mode: ReferenceMode,
    swipl: str,
    include_matrices: bool,
) -> list[str]:
    command = [
        "uv",
        "run",
        "--package",
        "connections",
        "python",
        _parity_script(kind),
        "--json",
        "--path",
        str(problem_path),
        "--logic",
        sweep.logic,
        "--domain",
        sweep.domain,
        "--reference",
        sweep.reference,
        "--swipl",
        swipl,
        "--timeout",
        str(timeout_seconds),
    ]
    if kind in {"status_check", "trace"}:
        command.extend(["--reference-mode", reference_mode])
    if kind == "matrix" and not include_matrices:
        command.append("--omit-matrices")
    for setting in sweep.settings:
        command.extend(["--settings", setting])
    for source_dir in sweep.source_dirs:
        command.extend(["--source-dir", str(source_dir)])
    return command


def _parity_script(kind: SweepKind) -> str:
    if kind == "status_check":
        return "tools/parity/run_status_check.py"
    return f"tools/parity/run_{kind}_parity.py"


def _diagnose_command(
    sweep: ParitySweep,
    *,
    problem_path: Path,
    timeout_seconds: float,
) -> list[str]:
    command = [
        "uv",
        "run",
        "--package",
        "connections",
        "python",
        "tools/parity/diagnose_search.py",
        str(problem_path),
        "--logic",
        sweep.logic,
        "--domain",
        sweep.domain,
        "--timeout",
        str(timeout_seconds),
        "--json",
    ]
    for setting in sweep.settings:
        command.extend(["--settings", setting])
    for source_dir in sweep.source_dirs:
        command.extend(["--source-dir", str(source_dir)])
    return command


class _optional_jsonl_writer:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._file = None

    def __enter__(self):
        if self.path is None:
            return lambda row: None
        self._file = self.path.open("w", encoding="utf-8")

        def write(row: Mapping[str, Any]) -> None:
            assert self._file is not None
            self._file.write(json.dumps(row, sort_keys=True) + "\n")

        return write

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._file is not None:
            self._file.close()


def _summary_output_path(
    output: Path | None,
    args: argparse.Namespace,
) -> Path | None:
    if args.no_summary:
        return None
    if args.summary_out is not None:
        return Path(args.summary_out)
    if output is None:
        return None
    return output.with_suffix(".summary.json")


def _run_summary(
    summaries: list[dict[str, Any]],
    *,
    manifest: Path,
    output: Path | None,
    summary_output: Path | None,
) -> dict[str, Any]:
    return {
        "schema": "connections.parity_manifest_run_summary.v1",
        "manifest": str(manifest),
        "output": None if output is None else str(output),
        "summary_output": None if summary_output is None else str(summary_output),
        "sweeps": summaries,
        "sweep_count": len(summaries),
        "rows": sum(int(summary["rows"]) for summary in summaries),
        "failures": sum(int(summary["failures"]) for summary in summaries),
        "classified": sum(int(summary["classified"]) for summary in summaries),
        "native_timeouts": sum(
            int(summary.get("native_timeouts", 0)) for summary in summaries
        ),
        "reference_timeouts": sum(
            int(summary.get("reference_timeouts", 0)) for summary in summaries
        ),
        "status_divergences": sum(
            int(summary.get("status_divergences", 0)) for summary in summaries
        ),
        "expected_status_rows": sum(
            int(summary.get("expected_status_rows", 0)) for summary in summaries
        ),
        "unlabeled_status_rows": sum(
            int(summary.get("unlabeled_status_rows", 0)) for summary in summaries
        ),
        "native_expected_failures": sum(
            int(summary.get("native_expected_failures", 0)) for summary in summaries
        ),
        "skipped": sum(summary["status"] == "skipped" for summary in summaries),
        "status": "ok"
        if all(summary["status"] in {"ok", "skipped"} for summary in summaries)
        else "failed",
    }


def _check_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; pass --overwrite to replace it")


__all__ = ["ParitySweep", "build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
