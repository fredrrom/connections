from __future__ import annotations

import argparse
from dataclasses import replace
import logging
from pathlib import Path
import sys
import traceback
from typing import Any

from connections.prover.prover import Prover, ProverHook, StrategyResult
from connections.prover.strategy import (
    ScheduledStrategy,
    StrategySchedule,
    WeightedStrategy,
)
from connections.pycop.schedule import load_schedule_entries
from connections.pycop.settings_codec import LeancopSettingsCodec
from connections.pycop.strategy import PycopStrategy
from connections.trace_logging import (
    CLAUSIFICATION_TRACE_LOGGER_NAME,
    TRACE_LEVEL,
    TRACE_LOGGER_NAME,
)

TRACE_HANDLER_MARKER = "_connections_cli_trace_handler"


class _ScheduleReportHook(ProverHook):
    def on_strategy_start(
        self,
        strategy_index: int,
        entry: ScheduledStrategy[Any],
    ) -> None:
        strategy = entry.strategy
        if not isinstance(strategy, PycopStrategy):
            raise TypeError("pycop schedule reporting requires PycopStrategy entries")
        tokens = LeancopSettingsCodec.to_tokens(strategy)
        print(
            f"strategy {strategy_index + 1}: tokens=[{','.join(tokens)}], "
            f"translation={strategy.matrix.translation}, "
            f"start={strategy.matrix.start_clauses}, "
            f"cut={strategy.dfs.cut}, "
            f"scut={strategy.dfs.scut}, comp={strategy.id.comp}, "
            f"steps={entry.step_limit}, seconds={entry.timeout_seconds}"
        )

    def on_strategy_end(
        self,
        result: StrategyResult[Any],
        state: Any,
    ) -> None:
        _ = state
        print(None if result.szs_status is None else result.szs_status.value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connections Python connection-tableau prover"
    )
    parser.add_argument("file", help="The conjecture you want to prove")
    parser.add_argument(
        "logic",
        nargs="?",
        default="classical",
        choices=("classical", "intuitionistic", "D", "T", "S4", "S5"),
        help="Which logic",
    )
    parser.add_argument(
        "domain",
        nargs="?",
        default="constant",
        choices=("constant", "cumulative", "varying"),
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
        help="Print machine-readable run metrics for benchmark tooling",
    )
    parser.add_argument(
        "--backtrack",
        choices=("step", "maximal"),
        default="step",
        help="Undo one exhausted inference at a time or one maximal failed subtree",
    )
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


def source_file_dirs_from_args(source_dir: str | None) -> tuple[Path, ...]:
    return () if source_dir is None else (Path(source_dir).resolve(),)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        configure_trace_loggers(
            search=args.trace_search,
            clausification=args.trace_clausification,
        )
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
        prover = Prover()
        hooks: list[ProverHook] = []
        if args.schedule:
            hooks.append(_ScheduleReportHook())
        if not args.schedule:
            run_result = prover.run(
                args.file,
                strategy=schedule.entries[0],
                logic=args.logic,
                domain=args.domain,
                source_file_dirs=source_file_dirs,
                hooks=hooks,
            )
            result = run_result.strategy_results[0]
            print(None if result.szs_status is None else result.szs_status.value)
            if args.metrics:
                print(f"METRIC inference_actions={result.inference_actions}")
            return 0

        prover.run(
            args.file,
            schedule=schedule,
            logic=args.logic,
            domain=args.domain,
            source_file_dirs=source_file_dirs,
            hooks=hooks,
        )
        return 0
    except Exception:
        traceback.print_exc()
        return 1


def _with_backtrack(
    entry: WeightedStrategy[PycopStrategy],
    *,
    backtrack: str,
) -> WeightedStrategy[PycopStrategy]:
    return replace(
        entry,
        strategy=replace(
            entry.strategy,
            dfs=replace(entry.strategy.dfs, backtrack=backtrack),
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
