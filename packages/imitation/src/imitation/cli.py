"""Command line entry point: DAgger experiments over a problem corpus.

One command reproduces the training and evaluation loop of the paper:
select problems, hold some out, train the DAgger agent within a total step
budget, and report the measures -- success J_S, search cost J_T, proof
size J_L, directness J_D -- for every training pass and for the base and
learned policies on the held-out problems.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from connections.agent import MarkovAgent, OnlineDFSAgent, OnlineIDAgent
from connections.corpora import workspace_root
from connections.interaction.run import Problem

from imitation.actor_learner import DAggerAgent, first_action
from imitation.experiment import (
    EpisodeRecord,
    aggregate,
    evaluate,
    retention,
    run_experiment,
)
from imitation.learning.trainer import SupervisedLearner, TrainingConfig
from imitation.model import GraphModelConfig
from imitation.performance import AllActionsMarkovAgent, PerformanceRecipe
from imitation.records import write_examples
from imitation.tasks import holdout_split

SURFACES = {
    "id": OnlineIDAgent,
    "dfs": OnlineDFSAgent,
    "markov": MarkovAgent,
    "all-actions": AllActionsMarkovAgent,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="imitation-experiment",
        description="Train and evaluate a DAgger agent on a problem corpus.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("problems", type=Path, help="Problem directory or file.")
    parser.add_argument("--pattern", default="*.p", help="Glob under the directory.")
    parser.add_argument("--limit", type=int, default=None, help="Cap the corpus size.")
    parser.add_argument("--seed", type=int, default=0, help="Selection/split seed.")
    parser.add_argument(
        "--holdout",
        type=float,
        default=0.0,
        help="Fraction of problems held out for evaluation.",
    )
    parser.add_argument(
        "--surface",
        choices=sorted(SURFACES),
        default="id",
        help="Search agent the learned chooser acts through.",
    )
    parser.add_argument("--horizon", type=int, default=100, help="Steps per episode.")
    parser.add_argument(
        "--total-steps",
        type=int,
        default=1_000_000,
        help="Total interaction budget across all episodes.",
    )
    parser.add_argument("--episodes-per-problem", type=int, default=1)
    parser.add_argument(
        "--timeout", type=float, default=None, help="Seconds per episode."
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Concurrent episodes."
    )
    parser.add_argument("--hidden", type=int, default=64, help="Model width.")
    parser.add_argument("--rounds", type=int, default=3, help="Message rounds.")
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument(
        "--lr-schedule",
        choices=("none", "cosine"),
        default="none",
        help="Anneal the learning rate over the epoch budget.",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=None,
        help="Stop a round's training after this many non-improving epochs.",
    )
    parser.add_argument(
        "--target-accuracy",
        type=float,
        default=0.999,
        help="Stop a round's training at this train accuracy.",
    )
    parser.add_argument("--device", default="auto", help="Training device.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Per-episode and per-epoch diagnostics.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Warnings only.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / "imitation",
        help="Checkpoints and collected examples land here.",
    )
    return parser


def select_problems(
    root: Path, *, pattern: str, limit: int | None, seed: int
) -> tuple[Problem, ...]:
    if not root.exists() and not root.is_absolute():
        # Corpora are centralized at the workspace root, so a relative path
        # not found here is retried against it.
        anchor = workspace_root()
        if anchor is not None and (anchor / root).exists():
            root = anchor / root
    if not root.exists():
        raise SystemExit(
            f"{root} does not exist; fetch the paper's corpora first, e.g. "
            "`uv run connections-download-corpora m2k mptp2078 tptp-v9.2.1`"
        )
    if root.is_file():
        paths = [root]
    else:
        paths = sorted(root.rglob(pattern))
    if not paths:
        raise SystemExit(f"no problems under {root} matching {pattern!r}")
    random.Random(seed).shuffle(paths)
    if limit is not None:
        paths = paths[:limit]
    return tuple(Problem(path) for path in paths)


def report_measures(label: str, records: Iterable[EpisodeRecord]) -> None:
    measures = aggregate(record.measures for record in records)
    j_t = "-" if measures.j_t is None else f"{measures.j_t:8.1f}"
    j_l = "-" if measures.j_l is None else f"{measures.j_l:6.1f}"
    j_d = "-" if measures.j_d is None else f"{measures.j_d:5.2f}"
    print(
        f"  {label:<20} solved {measures.successes:4d}/{measures.attempts:<4d}"
        f"  J_S {measures.j_s:5.3f}  J_T {j_t}  J_L {j_l}  J_D {j_d}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    level = (
        logging.DEBUG
        if args.verbose
        else logging.WARNING
        if args.quiet
        else logging.INFO
    )
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname).1s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    problems = select_problems(
        args.problems, pattern=args.pattern, limit=args.limit, seed=args.seed
    )
    train, held_out = holdout_split(
        problems, holdout_fraction=args.holdout, seed=args.seed
    )
    print(f"corpus: {len(train)} training problems, {len(held_out)} held out")

    recipe = PerformanceRecipe(agent_class=SURFACES[args.surface])
    agent = DAggerAgent(
        recipe,
        output_dir=args.output,
        learner=SupervisedLearner(
            model_config=GraphModelConfig(
                hidden_dim=args.hidden, message_rounds=args.rounds
            ),
            training=TrainingConfig(
                epochs=args.epochs,
                batch_size=args.batch_size,
                learning_rate=args.lr,
                lr_schedule=args.lr_schedule,
                patience=args.patience,
                target_train_accuracy=args.target_accuracy,
                seed=args.seed,
                device=args.device,
            ),
            device="cpu",
        ),
    )
    executor = None if args.workers <= 1 else ThreadPoolExecutor(args.workers)
    try:
        report = run_experiment(
            agent,
            train,
            horizon=args.horizon,
            total_steps=args.total_steps,
            episodes_per_problem=args.episodes_per_problem,
            timeout_seconds=args.timeout,
            executor=executor,
        )
        print("== training ==")
        for pass_report in report.passes:
            report_measures(f"pass {pass_report.pass_index}", pass_report.records)
        for index, step in enumerate(retention(report)):
            print(
                f"  retention {index}->{index + 1}: kept {len(step.kept)},"
                f" gained {len(step.gained)}, lost {len(step.lost)}"
            )
        print(
            f"  steps spent {report.steps_spent}, rounds {agent.round_index},"
            f" examples {len(agent.experience())},"
            f" replay failures {len(agent.critic.failures)}"
        )

        if held_out:
            print(f"== held-out evaluation (horizon {args.horizon}) ==")
            base = evaluate(
                lambda: recipe.with_chooser(first_action),
                held_out,
                horizon=args.horizon,
                timeout_seconds=args.timeout,
                executor=executor,
            )
            report_measures("base (first)", base.records())
            if agent.model is not None:
                learned = evaluate(
                    agent.performance_copy,
                    held_out,
                    horizon=args.horizon,
                    timeout_seconds=args.timeout,
                    executor=executor,
                )
                report_measures("learned", learned.records())
    finally:
        if executor is not None:
            executor.shutdown()

    args.output.mkdir(parents=True, exist_ok=True)
    examples_path = args.output / "examples.jsonl"
    write_examples(examples_path, agent.experience())
    print(f"examples written to {examples_path}")
    return 0


__all__ = ["build_parser", "main"]
