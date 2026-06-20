from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
import importlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
from typing import Any, Generic, TypeVar

from connections.syntax.logic import Domain, Logic
from connections.prover.status import ProverOutcome, SZSStatus
from connections.prover.prover import (
    ProblemSpec,
    ProofFoundCallback,
    Prover,
    ProverResult,
)
from connections.prover.strategy import Strategy, StrategySchedule

ProblemRunner = Callable[[Path], ProverResult[Any]]
StrategyT = TypeVar("StrategyT", bound=Strategy)


_WORKER_SCHEDULE: StrategySchedule[Any] | None = None
_WORKER_LOGIC: Logic = "classical"
_WORKER_DOMAIN: Domain = "constant"
_WORKER_SOURCE_FILE_DIRS: tuple[str | Path, ...] = ()
_WORKER_ON_PROOF_FOUND: ProofFoundCallback[Any] | None = None


@dataclass(frozen=True, slots=True)
class RunRow:
    problem: str
    path: str
    status: str | None
    outcome: str | None
    szs_status: str | None
    steps: int
    inference_actions: int
    elapsed_seconds: float
    strategy_count: int
    winning_strategy_index: int | None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RunRecord(Generic[StrategyT]):
    index: int
    path: Path
    row: RunRow
    result: ProverResult[StrategyT] | None = None
    proof_payload: Any | None = None
    error: BaseException | None = None


def select_problem_paths(
    roots: Sequence[str | Path],
    *,
    pattern: str = "*.p",
    recursive: bool = True,
    limit: int | None = None,
    offset: int = 0,
    shuffle: bool = False,
    seed: int = 0,
) -> tuple[Path, ...]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if offset < 0:
        raise ValueError("offset must be non-negative")

    paths: list[Path] = []
    for root in roots:
        paths.extend(_paths_from_root(Path(root), pattern=pattern, recursive=recursive))

    unique = sorted({path.resolve() for path in paths})
    if shuffle:
        random.Random(seed).shuffle(unique)
    if offset:
        unique = unique[offset:]
    if limit is not None:
        unique = unique[:limit]
    return tuple(unique)


def run_corpus(
    problem_paths: Iterable[str | Path],
    *,
    run_problem: ProblemRunner | None = None,
    schedule: StrategySchedule[Any] | None = None,
    logic: Logic = "classical",
    domain: Domain = "constant",
    source_file_dirs: Sequence[str | Path] = (),
    continue_on_error: bool = False,
    jobs: int = 1,
    worker_threads: int = 1,
    retain_result: bool = True,
    on_proof_found: ProofFoundCallback[Any] | None = None,
    yield_order: str = "input",
) -> Iterator[RunRow]:
    for record in run_corpus_records(
        problem_paths,
        run_problem=run_problem,
        schedule=schedule,
        logic=logic,
        domain=domain,
        source_file_dirs=source_file_dirs,
        continue_on_error=continue_on_error,
        jobs=jobs,
        worker_threads=worker_threads,
        retain_result=retain_result,
        on_proof_found=on_proof_found,
        yield_order=yield_order,
    ):
        yield record.row


def run_corpus_records(
    problem_paths: Iterable[str | Path],
    *,
    run_problem: ProblemRunner | None = None,
    schedule: StrategySchedule[StrategyT] | None = None,
    logic: Logic = "classical",
    domain: Domain = "constant",
    source_file_dirs: Sequence[str | Path] = (),
    continue_on_error: bool = False,
    jobs: int = 1,
    worker_threads: int = 1,
    retain_result: bool = True,
    on_proof_found: ProofFoundCallback[StrategyT] | None = None,
    yield_order: str = "input",
) -> Iterator[RunRecord[StrategyT]]:
    paths = tuple(Path(path).resolve() for path in problem_paths)
    if run_problem is None and schedule is None:
        raise ValueError("run_corpus_records requires either run_problem or schedule")
    if jobs < 1:
        raise ValueError("jobs must be positive")
    if worker_threads < 1:
        raise ValueError("worker_threads must be positive")
    if yield_order not in {"input", "completion"}:
        raise ValueError("yield_order must be 'input' or 'completion'")
    if jobs == 1 or len(paths) <= 1:
        if run_problem is None:
            if schedule is None:
                raise ValueError(
                    "run_corpus_records requires either run_problem or schedule"
                )
            runner = _scheduled_problem_runner(
                schedule=schedule,
                logic=logic,
                domain=domain,
                source_file_dirs=source_file_dirs,
                on_proof_found=on_proof_found,
            )
        else:
            runner = run_problem
        for index, problem_path in enumerate(paths):
            record = _run_record(
                index,
                problem_path,
                run_problem=runner,
                continue_on_error=continue_on_error,
                retain_result=retain_result,
            )
            yield record
        return
    if run_problem is not None:
        raise ValueError("parallel run_corpus_records requires a schedule")

    completed: list[RunRecord[StrategyT]] = []
    pool = _process_context().Pool(
        processes=min(jobs, len(paths)),
        initializer=_initialize_worker,
        initargs=(
            schedule,
            logic,
            domain,
            tuple(source_file_dirs),
            on_proof_found,
            worker_threads,
        ),
    )
    try:
        tasks = tuple(
            (index, str(problem_path), continue_on_error, retain_result)
            for index, problem_path in enumerate(paths)
        )
        for record in pool.imap_unordered(_run_scheduled_record_worker_task, tasks):
            if yield_order == "input":
                completed.append(record)
            else:
                yield record
    except BaseException:
        pool.terminate()
        raise
    else:
        pool.close()
    finally:
        pool.join()
    if yield_order == "input":
        yield from sorted(completed, key=lambda record: record.index)


def row_from_result(
    path: str | Path,
    result: ProverResult[Any],
    *,
    problem: str | None = None,
) -> RunRow:
    return RunRow(
        problem=problem or Path(path).name,
        path=str(path),
        status=_status_value(result.szs_status),
        outcome=_outcome_value(result.outcome),
        szs_status=_status_value(result.szs_status),
        steps=sum(strategy.steps for strategy in result.strategy_results),
        inference_actions=sum(
            strategy.inference_actions for strategy in result.strategy_results
        ),
        elapsed_seconds=sum(
            strategy.elapsed_seconds for strategy in result.strategy_results
        ),
        strategy_count=len(result.strategy_results),
        winning_strategy_index=result.winning_strategy_index,
    )


def row_from_error(
    path: str | Path,
    error: BaseException,
    *,
    problem: str | None = None,
) -> RunRow:
    return RunRow(
        problem=problem or Path(path).name,
        path=str(path),
        status=SZSStatus.ERROR.value,
        outcome=ProverOutcome.ERROR.value,
        szs_status=SZSStatus.ERROR.value,
        steps=0,
        inference_actions=0,
        elapsed_seconds=0.0,
        strategy_count=0,
        winning_strategy_index=None,
        error_type=type(error).__name__,
        error_message=str(error),
    )


def row_to_json(row: RunRow) -> dict[str, object]:
    return {
        "problem": row.problem,
        "path": row.path,
        "status": row.status,
        "outcome": row.outcome,
        "szs_status": row.szs_status,
        "steps": row.steps,
        "inference_actions": row.inference_actions,
        "elapsed_seconds": row.elapsed_seconds,
        "strategy_count": row.strategy_count,
        "winning_strategy_index": row.winning_strategy_index,
        "error_type": row.error_type,
        "error_message": row.error_message,
    }


def row_to_json_line(row: RunRow) -> str:
    return json.dumps(row_to_json(row), sort_keys=True)


def summarize_run_rows(
    rows: Sequence[RunRow],
    *,
    output: str | Path | None = None,
    summary_output: str | Path | None = None,
) -> dict[str, object]:
    return {
        "schema": "connections.runs_summary.v1",
        "output": None if output is None else str(output),
        "summary_output": None if summary_output is None else str(summary_output),
        "problems": len(rows),
        "theorem": _count_status(rows, "Theorem"),
        "unsatisfiable": _count_status(rows, "Unsatisfiable"),
        "counter_satisfiable": _count_status(rows, "CounterSatisfiable"),
        "satisfiable": _count_status(rows, "Satisfiable"),
        "timeout": _count_status(rows, "Timeout"),
        "gave_up": _count_status(rows, "GaveUp"),
        "error": _count_status(rows, "Error"),
        "steps": sum(row.steps for row in rows),
        "inference_actions": sum(row.inference_actions for row in rows),
    }


def _paths_from_root(root: Path, *, pattern: str, recursive: bool) -> tuple[Path, ...]:
    if root.is_file():
        return (root,)
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise ValueError(f"problem root is neither a file nor directory: {root}")
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    return tuple(path for path in iterator if path.is_file())


def _scheduled_problem_runner(
    *,
    schedule: StrategySchedule[Any],
    logic: Logic,
    domain: Domain,
    source_file_dirs: Sequence[str | Path],
    on_proof_found: ProofFoundCallback[Any] | None = None,
) -> ProblemRunner:
    prover = Prover()
    source_dirs = tuple(source_file_dirs)

    def run_problem(problem_path: Path) -> ProverResult[Any]:
        problem = ProblemSpec(
            problem_path,
            logic=logic,
            domain=domain,
            source_file_dirs=source_dirs,
        )
        return prover.run(
            problem,
            schedule=schedule,
            on_proof_found=on_proof_found,
        )

    return run_problem


def _run_record(
    index: int,
    problem_path: Path,
    *,
    run_problem: ProblemRunner,
    continue_on_error: bool,
    retain_result: bool,
) -> RunRecord[Any]:
    try:
        result = run_problem(problem_path)
        return RunRecord(
            index=index,
            path=problem_path,
            row=row_from_result(problem_path, result),
            result=result if retain_result else None,
            proof_payload=result.proof_payload,
        )
    except Exception as err:
        if not continue_on_error:
            raise
        return RunRecord(
            index=index,
            path=problem_path,
            row=row_from_error(problem_path, err),
            error=err,
        )


def _run_scheduled_record_worker(
    index: int,
    problem_path: str,
    continue_on_error: bool,
    retain_result: bool,
) -> RunRecord[Any]:
    schedule = _WORKER_SCHEDULE
    if schedule is None:
        raise RuntimeError("run_corpus worker was not initialized")
    runner = _scheduled_problem_runner(
        schedule=schedule,
        logic=_WORKER_LOGIC,
        domain=_WORKER_DOMAIN,
        source_file_dirs=_WORKER_SOURCE_FILE_DIRS,
        on_proof_found=_WORKER_ON_PROOF_FOUND,
    )
    return _run_record(
        index,
        Path(problem_path),
        run_problem=runner,
        continue_on_error=continue_on_error,
        retain_result=retain_result,
    )


def _run_scheduled_record_worker_task(
    task: tuple[int, str, bool, bool],
) -> RunRecord[Any]:
    index, problem_path, continue_on_error, retain_result = task
    return _run_scheduled_record_worker(
        index,
        problem_path,
        continue_on_error,
        retain_result,
    )


def _initialize_worker(
    schedule: StrategySchedule[Any] | None,
    logic: Logic,
    domain: Domain,
    source_file_dirs: Sequence[str | Path],
    on_proof_found: ProofFoundCallback[Any] | None,
    worker_threads: int,
) -> None:
    _configure_worker_threads(worker_threads)
    _set_worker_inputs(
        schedule=schedule,
        logic=logic,
        domain=domain,
        source_file_dirs=source_file_dirs,
        on_proof_found=on_proof_found,
    )


def _set_worker_inputs(
    *,
    schedule: StrategySchedule[Any] | None,
    logic: Logic,
    domain: Domain,
    source_file_dirs: Sequence[str | Path],
    on_proof_found: ProofFoundCallback[Any] | None,
) -> None:
    global _WORKER_SCHEDULE
    global _WORKER_LOGIC
    global _WORKER_DOMAIN
    global _WORKER_SOURCE_FILE_DIRS
    global _WORKER_ON_PROOF_FOUND

    _WORKER_SCHEDULE = schedule
    _WORKER_LOGIC = logic
    _WORKER_DOMAIN = domain
    _WORKER_SOURCE_FILE_DIRS = tuple(source_file_dirs)
    _WORKER_ON_PROOF_FOUND = on_proof_found


def _process_context() -> mp.context.BaseContext:
    methods = mp.get_all_start_methods()
    for method in ("spawn", "forkserver", "fork"):
        if method in methods:
            return mp.get_context(method)
    return mp.get_context(methods[0])


def _configure_worker_threads(threads: int = 1) -> None:
    value = str(threads)
    os.environ["OMP_NUM_THREADS"] = value
    os.environ["MKL_NUM_THREADS"] = value
    os.environ["OPENBLAS_NUM_THREADS"] = value
    os.environ["NUMEXPR_NUM_THREADS"] = value
    os.environ["VECLIB_MAXIMUM_THREADS"] = value
    try:
        torch = importlib.import_module("torch")
    except Exception:
        return
    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(threads)
    except RuntimeError:
        pass


def _status_value(status: SZSStatus | None) -> str | None:
    return None if status is None else status.value


def _outcome_value(outcome: ProverOutcome | None) -> str | None:
    return None if outcome is None else outcome.value


def _count_status(rows: Sequence[RunRow], status: str) -> int:
    return sum(row.status == status for row in rows)


__all__ = [
    "ProblemRunner",
    "RunRecord",
    "RunRow",
    "row_from_error",
    "row_from_result",
    "row_to_json",
    "row_to_json_line",
    "run_corpus",
    "run_corpus_records",
    "select_problem_paths",
    "summarize_run_rows",
]
