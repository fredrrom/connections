from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time
from typing import Any, Sequence, cast

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from connections.clausification import matrix_from_file
from connections.constraints.prefix import prefix_equations_satisfiable
from connections.constraints.prefix_types import PrefixEquation
from connections.constraints.term import TermBinding
from connections.syntax.formula import Prefix
from connections.syntax.logic import Domain, Logic
from connections.syntax.matrix import Clause, Literal
from connections.prover.status import ProverOutcome, to_szs_status
from connections.prover.actions import Action, ApplyAction, UndoAction
from connections.prover.dynamics import Dynamics
from connections.prover.prover import Problem
from connections.prover.rules import Extension, Factorization, Reduction, Start
from connections.prover.state import State
from connections.prover.strategy import MatrixOptions
from connections.prover.tableau import Tableau, TableauNode
from provers.pycop.settings_codec import LeancopSettingsCodec


@dataclass(slots=True)
class SearchAudit:
    counts: Counter[str] = field(default_factory=Counter)
    witnesses: list[dict[str, object]] = field(default_factory=list)
    witness_limit: int = 20

    def count(self, key: str, amount: int = 1) -> None:
        self.counts[key] += amount

    def witness(
        self,
        *,
        kind: str,
        reason: str,
        goal: TableauNode,
        left: Literal,
        right: Literal,
        equation: PrefixEquation | None,
        current_prefix_equation_count: int,
    ) -> None:
        if len(self.witnesses) >= self.witness_limit:
            return
        self.witnesses.append(
            {
                "kind": kind,
                "reason": reason,
                "goal_id": goal.goal_id,
                "goal_depth": goal.depth,
                "left": _literal_summary(left),
                "right": _literal_summary(right),
                "equation": None if equation is None else _equation_summary(equation),
                "current_prefix_equations": current_prefix_equation_count,
            }
        )


def diagnose(
    path: Path,
    *,
    logic: Logic,
    domain: Domain,
    settings: tuple[str, ...],
    source_file_dirs: Sequence[str | Path],
    max_choices: int,
    step_limit: int | None,
    timeout_seconds: float | None,
    witness_limit: int,
) -> dict[str, Any]:
    strategy = LeancopSettingsCodec.from_tokens(list(settings))
    state = _build_state(
        path,
        matrix_options=strategy.matrix,
        logic=logic,
        domain=domain,
        source_file_dirs=source_file_dirs,
    )
    policy = strategy.policy.instantiate()
    replay_policy = cast(Any, policy)
    audit = SearchAudit(witness_limit=witness_limit)
    started_at = time.monotonic()
    deadline = None if timeout_seconds is None else started_at + timeout_seconds
    inference_actions = 0
    choices = 0
    outcome: ProverOutcome | None = None

    while outcome is None:
        if state.tableau.root.closed:
            outcome = ProverOutcome.PROVED
            break
        if choices >= max_choices:
            outcome = ProverOutcome.STEP_BUDGET
            break
        if deadline is not None and time.monotonic() >= deadline:
            outcome = ProverOutcome.TIMEOUT
            break

        audit_state(state, audit=audit)
        actions = replay_policy._available_actions(state)
        output = (
            replay_policy._exhausted_outcome()
            if not actions
            else replay_policy._next_action(state, actions)
        )
        choices += 1

        if isinstance(output, ProverOutcome):
            outcome = output
            break
        if output is None:
            break

        action = output
        replay_policy._after_action(state, actions, action)
        _audit_choice(actions, action, audit=audit)
        if isinstance(action, ApplyAction):
            if step_limit is not None and inference_actions >= step_limit:
                outcome = ProverOutcome.STEP_BUDGET
                break
            inference_actions += 1
        Dynamics.transition(state, action)

    szs_status = to_szs_status(
        outcome,
        has_conjecture=state.problem.has_conjecture,
    )
    return {
        "schema": "connections.search_diagnostic.v1",
        "path": str(path.resolve()),
        "logic": logic,
        "domain": domain,
        "settings": list(settings),
        "decoded_settings": LeancopSettingsCodec.to_tokens(strategy),
        "matrix": {
            "clauses": len(state.problem.matrix.clauses),
            "positive_start_clauses": len(state.problem.matrix.positive_clauses),
            "conjecture_clauses": len(state.problem.matrix.conjecture_clauses),
            "source_has_conjecture": state.problem.matrix.source_has_conjecture,
        },
        "outcome": None if outcome is None else outcome.value,
        "szs_status": None if szs_status is None else szs_status.value,
        "choices": choices,
        "inference_actions": inference_actions,
        "elapsed_seconds": time.monotonic() - started_at,
        "counts": dict(sorted(audit.counts.items())),
        "witnesses": audit.witnesses,
    }


def _build_state(
    path: Path,
    *,
    matrix_options: MatrixOptions,
    logic: Logic,
    domain: Domain,
    source_file_dirs: Sequence[str | Path],
) -> State:
    matrix = matrix_from_file(
        path,
        translation=matrix_options.translation,
        reorder=matrix_options.reorder,
        start_clauses=matrix_options.start_clauses,
        logic=logic,
        domain=domain,
        source_file_dirs=source_file_dirs,
    )
    return State(
        problem=Problem(
            matrix=matrix,
            start_clauses=matrix_options.start_clauses,
            logic=logic,
            domain=domain,
        ),
        tableau=Tableau(),
    )


def audit_state(state: State, *, audit: SearchAudit) -> None:
    audit.count("states")
    open_goals = tuple(_actionable_fringe_goals(state))
    audit.count("actionable_goals", len(open_goals))
    for goal in open_goals:
        if goal.goal_id == state.tableau.root_goal_id:
            _audit_start_goal(state, goal, audit=audit)
            continue
        regularity = Dynamics.regularity_violation(state, goal)
        if regularity is not None:
            audit.count("regularity_rejections")
            continue
        _audit_factorization_goal(state, goal, audit=audit)
        _audit_reduction_goal(state, goal, audit=audit)
        _audit_extension_goal(state, goal, audit=audit)


def _audit_start_goal(state: State, goal: TableauNode, *, audit: SearchAudit) -> None:
    for clause_idx in state.problem.start_clause_ids:
        clause = state.problem.matrix.clauses[clause_idx]
        audit.count("start_candidates")
        instance_id = _diagnostic_instance_id("start", clause_idx, 0)
        free_variables = _free_variable_refs(clause, instance_id)
        if state.constraints.delta_for_free_variables(
            free_variables,
            logic=state.problem.logic,
            domain=state.problem.domain,
        ) is None:
            audit.count("start_rejected_free_variables")
            literal = clause.literal(0) if clause.literal_count else _empty_literal()
            audit.witness(
                kind="start",
                reason="free_variables",
                goal=goal,
                left=literal,
                right=literal,
                equation=None,
                current_prefix_equation_count=len(state.constraints.prefix_equations),
            )
            continue
        audit.count("start_allowed")


def _audit_factorization_goal(
    state: State, goal: TableauNode, *, audit: SearchAudit
) -> None:
    target_context = state.literal_context_at(goal.goal_id)
    if target_context is None:
        return
    target_literal, target_instance = target_context
    sources = state.current_path_factorization_source_goal_ids_for(
        goal.goal_id,
        target_literal.signed_symbol,
    )
    audit.count("factorization_sources", len(sources))
    for source_id in sources:
        source_context = state.literal_context_at(source_id)
        if source_context is None:
            continue
        source_literal, source_instance = source_context
        if not state.constraints.satisfied_literals(
            source_literal,
            left_instance=source_instance,
            right=target_literal,
            right_instance=target_instance,
            logic=state.problem.logic,
            domain=state.problem.domain,
        ):
            audit.count("factorization_equal_rejected")
            continue
        audit.count("factorization_equal_allowed")


def _audit_reduction_goal(state: State, goal: TableauNode, *, audit: SearchAudit) -> None:
    target_context = state.literal_context_at(goal.goal_id)
    if target_context is None:
        return
    target_literal, target_instance = target_context
    sources = state.path_goal_ids_for(goal.goal_id, target_literal.complement_symbol)
    audit.count("reduction_sources", len(sources))
    for source_id in sources:
        source_context = state.literal_context_at(source_id)
        if source_context is None:
            continue
        source_literal, source_instance = source_context
        reason, equation = _classify_literal_pair(
            state,
            older=source_literal,
            older_instance=source_instance,
            newer=target_literal,
            newer_instance=target_instance,
            free_variables=(),
        )
        audit.count(f"reduction_{reason}")
        if reason != "allowed":
            audit.witness(
                kind="reduction",
                reason=reason,
                goal=goal,
                left=source_literal,
                right=target_literal,
                equation=equation,
                current_prefix_equation_count=len(state.constraints.prefix_equations),
            )


def _audit_extension_goal(state: State, goal: TableauNode, *, audit: SearchAudit) -> None:
    target_context = state.literal_context_at(goal.goal_id)
    if target_context is None or goal.clause_idx is None or goal.literal_index is None:
        return
    target_literal, target_instance = target_context
    for clause_idx, lit_idx in state.problem.matrix.complements(
        goal.clause_idx,
        goal.literal_index,
    ):
        audit.count("extension_candidates")
        clause = state.problem.matrix.clauses[clause_idx]
        selected_literal = clause.literal(lit_idx)
        instance_id = _diagnostic_instance_id("extension", clause_idx, lit_idx)
        reason, equation = _classify_literal_pair(
            state,
            older=target_literal,
            older_instance=target_instance,
            newer=selected_literal,
            newer_instance=instance_id,
            free_variables=_free_variable_refs(clause, instance_id),
        )
        audit.count(f"extension_{reason}")
        if reason != "allowed":
            audit.witness(
                kind="extension",
                reason=reason,
                goal=goal,
                left=target_literal,
                right=selected_literal,
                equation=equation,
                current_prefix_equation_count=len(state.constraints.prefix_equations),
            )


def _classify_literal_pair(
    state: State,
    *,
    older: Literal,
    older_instance: int | None,
    newer: Literal,
    newer_instance: int | None,
    free_variables: tuple[tuple[Any, int | None], ...],
) -> tuple[str, PrefixEquation | None]:
    if (
        state.problem.logic == "classical"
        and older.is_ground
        and newer.is_ground
    ):
        if older.atom == newer.atom:
            return "allowed", None
        return "term_rejected", None

    unifies, bindings = state.constraints.terms.unify_literals(
        older=older,
        older_instance=older_instance,
        newer=newer,
        newer_instance=newer_instance,
    )
    if not unifies:
        return "term_rejected", None

    prefix_reason, equation = _classify_prefix_pair(
        state,
        older=older,
        older_instance=older_instance,
        newer=newer,
        newer_instance=newer_instance,
        pending_bindings=bindings,
    )
    if prefix_reason != "allowed":
        return prefix_reason, equation

    if not state.constraints.free_variable_refs_admissible(
        free_variables,
        logic=state.problem.logic,
        domain=state.problem.domain,
        pending_bindings=bindings,
    ):
        return "free_variables_rejected", equation

    return "allowed", equation


def _classify_prefix_pair(
    state: State,
    *,
    older: Literal,
    older_instance: int | None,
    newer: Literal,
    newer_instance: int | None,
    pending_bindings: tuple[TermBinding, ...],
) -> tuple[str, PrefixEquation | None]:
    if state.problem.logic.lower() == "classical":
        return "allowed", None

    left_prefix, right_prefix = _oriented_substituted_prefixes(
        state,
        older=older,
        older_instance=older_instance,
        newer=newer,
        newer_instance=newer_instance,
        pending_bindings=pending_bindings,
    )
    equation = PrefixEquation(left_prefix, right_prefix)
    if equation.left == equation.right:
        return "allowed", equation
    if not prefix_equations_satisfiable(
        (equation,),
        logic=state.problem.logic,
        domain=state.problem.domain,
    ):
        return "prefix_local_rejected", equation
    if not prefix_equations_satisfiable(
        (*state.constraints.prefix_equations, equation),
        logic=state.problem.logic,
        domain=state.problem.domain,
    ):
        return "prefix_cumulative_rejected", equation
    return "allowed", equation


def _oriented_substituted_prefixes(
    state: State,
    *,
    older: Literal,
    older_instance: int | None,
    newer: Literal,
    newer_instance: int | None,
    pending_bindings: tuple[TermBinding, ...],
) -> tuple[Prefix, Prefix]:
    if state.problem.logic.lower() in {"intuitionistic", "intu"}:
        if older.polarity is False and newer.polarity is True:
            left, left_instance = older, older_instance
            right, right_instance = newer, newer_instance
        elif newer.polarity is False and older.polarity is True:
            left, left_instance = newer, newer_instance
            right, right_instance = older, older_instance
        else:
            left, left_instance = older, older_instance
            right, right_instance = newer, newer_instance
    else:
        left, left_instance = older, older_instance
        right, right_instance = newer, newer_instance

    return (
        state.constraints._substituted_prefix(  # noqa: SLF001
            _literal_prefix(left),
            left_instance,
            pending_bindings=pending_bindings,
        ),
        state.constraints._substituted_prefix(  # noqa: SLF001
            _literal_prefix(right),
            right_instance,
            pending_bindings=pending_bindings,
        ),
    )


def _audit_choice(
    actions: tuple[Action, ...],
    action: Action,
    *,
    audit: SearchAudit,
) -> None:
    audit.count("choices")
    audit.count(f"chosen_{_action_kind(action)}")
    audit.count("choice_action_count", len(actions))
    audit.count(f"chosen_index_{actions.index(action)}")
    audit.count("policy_action_spaces")
    audit.count("policy_available_actions", len(actions))
    for available_action in actions:
        audit.count(f"policy_available_{_action_kind(available_action)}")


def _actionable_fringe_goals(state: State) -> tuple[TableauNode, ...]:
    return tuple(
        goal
        for goal in state.fringe
        if not goal.closed and goal.applied_rule_application_id is None
    )


def _action_kind(action: Action) -> str:
    if isinstance(action, UndoAction):
        return "undo"
    if isinstance(action.rule, Start):
        return "start"
    if isinstance(action.rule, Extension):
        return "extension"
    if isinstance(action.rule, Reduction):
        return "reduction"
    if isinstance(action.rule, Factorization):
        return "factorization"
    return "unknown"


def _free_variable_refs(
    clause: Clause,
    instance_id: int | None,
) -> tuple[tuple[Any, int | None], ...]:
    return tuple((variable, instance_id) for variable in clause.free_variables)


def _literal_prefix(literal: Literal) -> Prefix:
    return Prefix(()) if literal.prefix is None else literal.prefix


def _diagnostic_instance_id(kind: str, clause_idx: int, lit_idx: int) -> int:
    offset = 1 if kind == "start" else 2
    return -((clause_idx + offset) * 100_000 + lit_idx + 1)


def _literal_summary(literal: Literal) -> dict[str, object]:
    return {
        "literal": str(literal),
        "polarity": literal.polarity,
        "predicate": literal.atom.symbol,
        "prefix": None if literal.prefix is None else str(literal.prefix),
    }


def _equation_summary(equation: PrefixEquation) -> dict[str, str]:
    return {
        "left": str(equation.left),
        "right": str(equation.right),
    }


def _empty_literal() -> Literal:
    from connections.syntax.formula import Atom

    return Literal(Atom("$empty", ()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose native pycop search candidate rejection for one problem."
    )
    parser.add_argument("path", type=Path)
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
        default=[],
        help="leanCoP setting token. May be repeated.",
    )
    parser.add_argument(
        "--source-dir",
        action="append",
        default=[],
        help="Directory used to resolve included TPTP files.",
    )
    parser.add_argument("--max-choices", type=int, default=10_000)
    parser.add_argument("--step-limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--witness-limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    row = diagnose(
        args.path,
        logic=args.logic,
        domain=args.domain,
        settings=tuple(args.settings),
        source_file_dirs=tuple(args.source_dir),
        max_choices=args.max_choices,
        step_limit=args.step_limit,
        timeout_seconds=args.timeout,
        witness_limit=args.witness_limit,
    )
    if args.json:
        print(json.dumps(row, sort_keys=True))
    else:
        _print_text(row)
    return 0


def _print_text(row: dict[str, Any]) -> None:
    print(
        f"{row['path']}: outcome={row['outcome']} "
        f"szs={row['szs_status']} choices={row['choices']} "
        f"inferences={row['inference_actions']}"
    )
    print(f"settings={row['decoded_settings']}")
    print("counts:")
    for key, value in row["counts"].items():
        print(f"  {key}: {value}")
    if row["witnesses"]:
        print("witnesses:")
        for witness in row["witnesses"]:
            print(json.dumps(witness, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
