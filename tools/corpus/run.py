from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.core.logic import Domain, Logic
from connections.prover.prover import Prover
from connections.prover.strategy import StrategySchedule
from connections.pycop.schedule import load_schedule_entries
from connections.pycop.settings_codec import LeancopSettingsCodec

from tools.corpus.records import (
    CorpusRunRow,
    row_from_error,
    row_from_result,
    row_to_json_line,
)
from tools.corpus.selection import select_problem_paths

ProverFactory = Callable[[], Prover]


def run_corpus(
    problem_paths: Iterable[str | Path],
    *,
    prover_factory: ProverFactory,
    schedule: StrategySchedule[Any] | None = None,
    strategy: Any | None = None,
    logic: Logic = "classical",
    domain: Domain = "constant",
    source_file_dirs: Sequence[str | Path] = (),
    continue_on_error: bool = False,
    problem_root: str | Path | None = None,
) -> Iterator[CorpusRunRow]:
    root = None if problem_root is None else Path(problem_root).resolve()
    for path in problem_paths:
        problem_path = Path(path).resolve()
        try:
            result = prover_factory().run(
                problem_path,
                strategy=strategy,
                schedule=schedule,
                logic=logic,
                domain=domain,
                source_file_dirs=source_file_dirs,
            )
            yield row_from_result(
                problem_path,
                result,
                problem=_problem_label(problem_path, root=root),
            )
        except Exception as err:
            if not continue_on_error:
                raise
            yield row_from_error(
                problem_path,
                err,
                problem=_problem_label(problem_path, root=root),
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a connections prover over a file or corpus."
    )
    parser.add_argument(
        "path",
        nargs="+",
        help="Problem file or directory. Directories are searched for problem files.",
    )
    parser.add_argument("--out", required=True, help="Output JSONL path")
    summary_group = parser.add_mutually_exclusive_group()
    summary_group.add_argument(
        "--summary-out",
        metavar="PATH",
        help="Output summary JSON path. Defaults to OUT with .summary.json suffix.",
    )
    summary_group.add_argument(
        "--no-summary",
        action="store_true",
        help="Do not write a summary JSON sidecar.",
    )
    parser.add_argument("--pattern", default="*.p")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--logic",
        default="classical",
        choices=("classical", "intuitionistic", "D", "T", "S4", "S5"),
    )
    parser.add_argument(
        "--domain",
        default="constant",
        choices=("constant", "cumulative", "varying"),
    )
    parser.add_argument(
        "--settings",
        "--setting",
        action="append",
        dest="settings",
        default=[],
        help="pycop strategy token; repeatable, e.g. --settings cut",
    )
    parser.add_argument("--schedule", metavar="PATH")
    parser.add_argument("--steps", type=_nonnegative_int, default=None)
    parser.add_argument("--timeout", type=_nonnegative_float, default=None)
    parser.add_argument(
        "--source-dir",
        action="append",
        default=[],
        help="Directory used to resolve included problem source files.",
    )
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--progress-every", type=int, default=25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.out)
    _check_writable(output, overwrite=args.overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_output = _summary_output_path(output, args)
    if summary_output is not None:
        if summary_output == output:
            raise ValueError("--summary-out must differ from --out")
        _check_writable(summary_output, overwrite=args.overwrite)
        summary_output.parent.mkdir(parents=True, exist_ok=True)

    problem_paths = select_problem_paths(
        args.path,
        pattern=args.pattern,
        recursive=not args.no_recursive,
        limit=args.limit,
        shuffle=args.shuffle,
        seed=args.seed,
    )
    schedule = _pycop_schedule_from_args(args)
    source_file_dirs = tuple(Path(path).resolve() for path in args.source_dir)

    rows: list[CorpusRunRow] = []
    with output.open("w", encoding="utf-8") as file:
        for index, row in enumerate(
            run_corpus(
                problem_paths,
                prover_factory=Prover,
                schedule=schedule,
                logic=args.logic,
                domain=args.domain,
                source_file_dirs=source_file_dirs,
                continue_on_error=args.continue_on_error,
                problem_root=_single_root(args.path),
            ),
            start=1,
        ):
            rows.append(row)
            file.write(row_to_json_line(row) + "\n")
            if _should_report_progress(index, len(problem_paths), args.progress_every):
                print(
                    f"progress={index}/{len(problem_paths)} "
                    f"theorem={_count_status(rows, 'Theorem')} "
                    f"errors={sum(row.error_type is not None for row in rows)}",
                    flush=True,
                )

    summary = _summary(rows, output=output, summary_output=summary_output)
    if summary_output is not None:
        summary_output.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _pycop_schedule_from_args(args: argparse.Namespace) -> StrategySchedule[Any]:
    if args.schedule and args.settings:
        raise ValueError("pass either --schedule or --settings, not both")
    if args.schedule:
        return StrategySchedule.from_weighted(
            load_schedule_entries(args.schedule),
            steps=args.steps,
            timeout_seconds=args.timeout,
        )
    return StrategySchedule.single(
        LeancopSettingsCodec.from_tokens(args.settings),
        steps=args.steps,
        timeout_seconds=args.timeout,
    )


def _problem_label(path: Path, *, root: Path | None) -> str:
    if root is None:
        return path.name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _single_root(paths: Sequence[str]) -> Path | None:
    if len(paths) != 1:
        return None
    root = Path(paths[0]).resolve()
    return root if root.is_dir() else root.parent


def _should_report_progress(index: int, total: int, every: int) -> bool:
    every = max(1, every)
    return index == total or index % every == 0


def _count_status(rows: Sequence[CorpusRunRow], status: str) -> int:
    return sum(row.status == status for row in rows)


def _summary(
    rows: Sequence[CorpusRunRow],
    *,
    output: Path,
    summary_output: Path | None = None,
) -> dict[str, object]:
    return {
        "schema": "connections.corpus_run_summary.v1",
        "output": str(output),
        "summary_output": None if summary_output is None else str(summary_output),
        "problems": len(rows),
        "theorem": _count_status(rows, "Theorem"),
        "unsatisfiable": _count_status(rows, "Unsatisfiable"),
        "counter_satisfiable": _count_status(rows, "CounterSatisfiable"),
        "satisfiable": _count_status(rows, "Satisfiable"),
        "timeout": _count_status(rows, "Timeout"),
        "gave_up": _count_status(rows, "GaveUp"),
        "error": _count_status(rows, "Error"),
        "inference_actions": sum(row.inference_actions for row in rows),
    }


def _summary_output_path(output: Path, args: argparse.Namespace) -> Path | None:
    if args.no_summary:
        return None
    if args.summary_out is not None:
        return Path(args.summary_out)
    if output.suffix:
        return output.with_suffix(".summary.json")
    return output.with_name(f"{output.name}.summary.json")


def _check_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise RuntimeError(f"{path} already exists; pass --overwrite")


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


__all__ = [
    "ProverFactory",
    "build_parser",
    "main",
    "run_corpus",
]


if __name__ == "__main__":
    raise SystemExit(main())
