from __future__ import annotations

import argparse
from dataclasses import replace
import json
import logging
from pathlib import Path
import sys
import traceback
from typing import Any, cast

from connections.syntax.logic import Domain, Logic
from connections.runs import (
    ProfileConfig,
    RunRow,
    profile_run_rows,
    row_to_json_line,
    run_corpus,
    select_problem_paths,
    summarize_run_rows,
)
from connections.prover.prover import (
    ProblemSpec,
    Prover,
    StrategyResult,
)
from connections.prover.strategy import (
    PolicyOptions,
    ScheduledStrategy,
    Strategy,
    StrategySchedule,
    WeightedStrategy,
)
from provers.pycop.schedule import load_schedule_entries
from provers.pycop.settings_codec import LeancopSettingsCodec
from connections.trace_logging import (
    CLAUSIFICATION_TRACE_LOGGER_NAME,
    TRACE_LEVEL,
    TRACE_LOGGER_NAME,
)

TRACE_HANDLER_MARKER = "_connections_cli_trace_handler"
LOGICS: tuple[Logic, ...] = ("classical", "intuitionistic", "D", "T", "S4", "S5")
DOMAINS: tuple[Domain, ...] = ("constant", "cumulative", "varying")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connections Python connection-tableau prover"
    )
    parser.add_argument(
        "path",
        nargs="+",
        help="Problem file or directory. Directories are searched for problem files.",
    )
    parser.add_argument(
        "--logic",
        default=None,
        choices=LOGICS,
        help="Which logic",
    )
    parser.add_argument(
        "--domain",
        default=None,
        choices=DOMAINS,
        help="Which domain",
    )
    parser.add_argument(
        "--trace-search",
        action="store_true",
        help="Print proof-search trace events",
    )
    parser.add_argument(
        "--trace-clausification",
        action="store_true",
        help="Print clausification and matrix-construction trace events",
    )
    parser.add_argument(
        "--schedule",
        metavar="PATH_OR_NAME",
        help=(
            "Run a strategy schedule from a JSON file, or a built-in schedule "
            "name: classical, intuitionistic, modal"
        ),
    )
    parser.add_argument(
        "--source-dir",
        action="append",
        default=[],
        metavar="PATH",
        help="Directory used to resolve included problem source files",
    )
    parser.add_argument(
        "--settings",
        "--setting",
        action="append",
        dest="settings",
        default=[],
        help="Strategy setting token (repeatable), e.g. --settings cut --settings comp(7)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=None,
        help="Maximum inference actions (all actions except bt)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum run time in seconds",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Print machine-readable run metrics for a single problem",
    )
    parser.add_argument(
        "--backtrack",
        choices=("step", "maximal"),
        default="step",
        help="Undo one exhausted inference at a time or one maximal failed subtree",
    )
    parser.add_argument("--out", metavar="PATH", help="Write corpus JSONL rows")
    parser.add_argument("--profile", metavar="DIR", help="Write cProfile run artifacts")
    parser.add_argument("--profile-sort", default="cumulative")
    parser.add_argument("--profile-limit-functions", type=_nonnegative_int, default=40)
    summary_group = parser.add_mutually_exclusive_group()
    summary_group.add_argument(
        "--summary-out",
        metavar="PATH",
        help="Output summary JSON path. Defaults to OUT with .summary.json suffix.",
    )
    summary_group.add_argument(
        "--no-summary",
        action="store_true",
        help="Do not write or print a corpus summary.",
    )
    parser.add_argument("--pattern", default="*.p")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--limit", type=_nonnegative_int, default=None)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--progress-every", type=int, default=25)
    return parser


def configure_trace_loggers(*, search: bool, clausification: bool) -> None:
    for logger_name, enabled in (
        (TRACE_LOGGER_NAME, search),
        (CLAUSIFICATION_TRACE_LOGGER_NAME, clausification),
    ):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            if getattr(handler, TRACE_HANDLER_MARKER, False):
                logger.removeHandler(handler)
        logger.propagate = False
        if not enabled:
            logger.setLevel(logging.WARNING)
            continue
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        setattr(handler, TRACE_HANDLER_MARKER, True)
        logger.addHandler(handler)
        logger.setLevel(TRACE_LEVEL)


def source_file_dirs_from_args(source_dirs: list[str]) -> tuple[Path, ...]:
    return tuple(Path(source_dir).resolve() for source_dir in source_dirs)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        configure_trace_loggers(
            search=args.trace_search,
            clausification=args.trace_clausification,
        )
        input_paths, logic, domain = _paths_logic_domain_from_args(args)
        source_file_dirs = source_file_dirs_from_args(args.source_dir)
        if args.schedule:
            if args.settings:
                raise ValueError("Do not combine --schedule with --settings")
            schedule_entries = load_schedule_entries(args.schedule)
        else:
            strategy = LeancopSettingsCodec.from_tokens(args.settings)
            schedule_entries = [WeightedStrategy(strategy=strategy, weight=1)]

        schedule_entries = [
            _with_backtrack(entry, backtrack=args.backtrack)
            for entry in schedule_entries
        ]

        schedule = StrategySchedule.from_weighted(
            schedule_entries,
            steps=args.steps,
            timeout_seconds=args.timeout,
        )
        problem_paths = select_problem_paths(
            input_paths,
            pattern=args.pattern,
            recursive=not args.no_recursive,
            limit=args.limit,
            shuffle=args.shuffle,
            seed=args.seed,
        )
        if not problem_paths:
            raise RuntimeError("no problem files found")
        if not _single_problem_mode(input_paths, args):
            return _run_corpus_mode(
                args,
                problem_paths=problem_paths,
                schedule=schedule,
                logic=logic,
                domain=domain,
                source_file_dirs=source_file_dirs,
            )

        problem = ProblemSpec(
            problem_paths[0],
            logic=logic,
            domain=domain,
            source_file_dirs=source_file_dirs,
        )
        prover = Prover()
        if not args.schedule:
            run_result = prover.run(
                problem,
                schedule=StrategySchedule(entries=(schedule.entries[0],)),
            )
            result = run_result.strategy_results[0]
            print(None if result.szs_status is None else result.szs_status.value)
            if args.metrics:
                print(f"METRIC inference_actions={result.inference_actions}")
            return 0

        run_result = prover.run(
            problem,
            schedule=schedule,
        )
        for index, result in enumerate(run_result.strategy_results):
            _print_schedule_report(index, schedule.entries[index], result)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


def _paths_logic_domain_from_args(
    args: argparse.Namespace,
) -> tuple[tuple[str, ...], Logic, Domain]:
    paths = list(args.path)
    logic = args.logic
    domain = args.domain
    if len(paths) >= 2 and paths[-2] in LOGICS and paths[-1] in DOMAINS:
        if logic is not None and logic != paths[-2]:
            raise ValueError("logic passed both positionally and with --logic")
        if domain is not None and domain != paths[-1]:
            raise ValueError("domain passed both positionally and with --domain")
        domain = paths.pop()
        logic = paths.pop()
    elif paths and paths[-1] in LOGICS:
        if logic is not None and logic != paths[-1]:
            raise ValueError("logic passed both positionally and with --logic")
        logic = paths.pop()
    if not paths:
        raise ValueError("pass at least one problem path")
    return (
        tuple(paths),
        cast(Logic, logic or "classical"),
        cast(Domain, domain or "constant"),
    )


def _single_problem_mode(paths: tuple[str, ...], args: argparse.Namespace) -> bool:
    return (
        args.out is None
        and args.profile is None
        and len(paths) == 1
        and Path(paths[0]).is_file()
        and not args.continue_on_error
        and not args.shuffle
        and args.limit is None
    )


def _run_corpus_mode(
    args: argparse.Namespace,
    *,
    problem_paths: tuple[Path, ...],
    schedule: StrategySchedule[Any],
    logic: Logic,
    domain: Domain,
    source_file_dirs: tuple[Path, ...],
) -> int:
    output = None if args.out is None else Path(args.out)
    profile_output = None if args.profile is None else Path(args.profile)
    if profile_output is not None:
        if output is not None:
            raise ValueError("--profile writes runs.jsonl itself; do not combine with --out")
        if args.summary_out is not None:
            raise ValueError("--profile writes summary.json itself; do not combine with --summary-out")
        _check_output_dir(profile_output, overwrite=args.overwrite)
        result = profile_run_rows(
            lambda: run_corpus(
                problem_paths,
                schedule=schedule,
                logic=logic,
                domain=domain,
                source_file_dirs=source_file_dirs,
                continue_on_error=args.continue_on_error,
            ),
            ProfileConfig(
                output_dir=profile_output,
                sort=args.profile_sort,
                limit_functions=args.profile_limit_functions,
                metadata={
                    "logic": logic,
                    "domain": domain,
                    "problems": len(problem_paths),
                },
                write_summary=not args.no_summary,
            ),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    summary_output = _summary_output_path(output, args)
    if output is not None:
        _check_writable(output, overwrite=args.overwrite)
        output.parent.mkdir(parents=True, exist_ok=True)
    if summary_output is not None:
        if output is not None and summary_output == output:
            raise ValueError("--summary-out must differ from --out")
        _check_writable(summary_output, overwrite=args.overwrite)
        summary_output.parent.mkdir(parents=True, exist_ok=True)

    rows: list[RunRow] = []
    if output is None:
        for index, row in enumerate(
            run_corpus(
                problem_paths,
                schedule=schedule,
                logic=logic,
                domain=domain,
                source_file_dirs=source_file_dirs,
                continue_on_error=args.continue_on_error,
            ),
            start=1,
        ):
            rows.append(row)
            print(row_to_json_line(row))
            _print_progress(index, len(problem_paths), rows, args.progress_every)
    else:
        with output.open("w", encoding="utf-8") as file:
            for index, row in enumerate(
                run_corpus(
                    problem_paths,
                    schedule=schedule,
                    logic=logic,
                    domain=domain,
                    source_file_dirs=source_file_dirs,
                    continue_on_error=args.continue_on_error,
                ),
                start=1,
            ):
                rows.append(row)
                file.write(row_to_json_line(row) + "\n")
                _print_progress(index, len(problem_paths), rows, args.progress_every)

    summary = summarize_run_rows(
        rows,
        output=output,
        summary_output=summary_output,
    )
    if summary_output is not None:
        summary_output.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if not args.no_summary:
        stream = sys.stdout if output is not None else sys.stderr
        print(json.dumps(summary, indent=2, sort_keys=True), file=stream)
    return 0


def _print_progress(
    index: int,
    total: int,
    rows: list[RunRow],
    every: int,
) -> None:
    if not _should_report_progress(index, total, every):
        return
    print(
        f"progress={index}/{total} "
        f"theorem={_count_status(rows, 'Theorem')} "
        f"errors={sum(row.error_type is not None for row in rows)}",
        file=sys.stderr,
        flush=True,
    )


def _should_report_progress(index: int, total: int, every: int) -> bool:
    every = max(1, every)
    return index == total or index % every == 0


def _count_status(rows: list[RunRow], status: str) -> int:
    return sum(row.status == status for row in rows)


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
    if output.suffix:
        return output.with_suffix(".summary.json")
    return output.with_name(f"{output.name}.summary.json")


def _check_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise RuntimeError(f"{path} already exists; pass --overwrite")


def _check_output_dir(path: Path, *, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise RuntimeError(f"{path} is not empty; pass --overwrite")


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


def _with_backtrack(
    entry: WeightedStrategy[Strategy],
    *,
    backtrack: str,
) -> WeightedStrategy[Strategy]:
    args = dict(entry.strategy.policy.args or {})
    args["backtrack"] = backtrack
    return replace(
        entry,
        strategy=replace(
            entry.strategy,
            policy=PolicyOptions(
                policy_class=entry.strategy.policy.policy_class,
                args=args,
            ),
        ),
    )


def _print_schedule_report(
    strategy_index: int,
    entry: ScheduledStrategy[Any],
    result: StrategyResult[Any],
) -> None:
    strategy = entry.strategy
    matrix = strategy.matrix
    args = dict(strategy.policy.args or {})
    tokens = LeancopSettingsCodec.to_tokens(strategy)
    print(
        f"strategy {strategy_index + 1}: tokens=[{','.join(tokens)}], "
        f"translation={matrix.translation}, "
        f"start={matrix.start_clauses}, "
        f"cut={args.get('cut', False)}, "
        f"scut={args.get('scut', False)}, comp={args.get('comp')}, "
        f"steps={entry.step_limit}, seconds={entry.timeout_seconds}"
    )
    print(None if result.szs_status is None else result.szs_status.value)


if __name__ == "__main__":
    raise SystemExit(main())
