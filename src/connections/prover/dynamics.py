from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from connections.syntax.matrix import Clause, Literal
from connections.constraints import FreeVariableReference
from connections.prover.actions import Action, ApplyAction, ApplyActions, UndoAction
from connections.prover.rules import (
    Extension,
    Factorization,
    FactorizationMode,
    Reduction,
    Rule,
    Start,
)
from connections.prover.state import State
from connections.prover.tableau import TableauNode
from connections.trace_logging import trace, trace_logger

RuleT = TypeVar("RuleT", bound=Rule)


class Dynamics:
    @staticmethod
    def apply_actions(
        state: State,
        goal: TableauNode,
        *,
        factorization: FactorizationMode = "unify",
    ) -> ApplyActions:
        if goal.closed:
            return ApplyActions()
        regularity_violation = Dynamics.regularity_violation(state, goal)
        if regularity_violation is not None:
            trace(trace_logger, "regularity")
            return ApplyActions()
        if goal.goal_id == state.tableau.root_goal_id:
            return ApplyActions(
                start=Dynamics._apply_actions(
                    goal.goal_id, Dynamics.start_rules_for(state, goal.goal_id)
                )
            )
        return ApplyActions(
            factorization=Dynamics._apply_actions(
                goal.goal_id,
                Dynamics.factorization_rules_for(
                    state, goal.goal_id, mode=factorization
                ),
            ),
            reduction=Dynamics._apply_actions(
                goal.goal_id, Dynamics.reduction_rules_for(state, goal.goal_id)
            ),
            extension=Dynamics._apply_actions(
                goal.goal_id, Dynamics.extension_rules_for(state, goal.goal_id)
            ),
        )

    @staticmethod
    def start_rules_for(state: State, _goal_id: int) -> tuple[Start, ...]:
        rules: list[Start] = []
        for idx in state.problem.start_clause_ids:
            clause = state.problem.matrix.clauses[idx]
            instance_id = state.fresh_instance_id()
            delta = state.constraints.delta_for_free_variables(
                ()
                if not clause.free_variables
                else Dynamics._free_variable_refs(clause, instance_id),
                logic=state.problem.logic,
                domain=state.problem.domain,
            )
            if delta is None:
                continue
            rules.append(
                Start(
                    clause=clause,
                    constraint_delta=delta,
                    clause_idx=idx,
                    instance_id=instance_id,
                )
            )
        return tuple(rules)

    @staticmethod
    def factorization_rules_for(
        state: State, goal_id: int, *, mode: FactorizationMode = "unify"
    ) -> tuple[Factorization, ...]:
        target_context = state.literal_context_at(goal_id)
        if target_context is None:
            return ()
        literal, literal_instance = target_context
        sources = state.current_path_factorization_source_goal_ids_for(
            goal_id, literal.signed_symbol
        )
        if not sources:
            return ()

        def make_rule(
            source_id: int,
            source_literal: Literal,
            source_instance: int | None,
            target_literal: Literal,
            target_instance: int | None,
        ) -> Factorization | None:
            if (
                state.problem.logic == "classical"
                and source_literal.is_ground
                and target_literal.is_ground
            ):
                if source_literal.atom != target_literal.atom:
                    return None
                if mode == "equal":
                    return Factorization(source_id, mode="equal")
                return Factorization(
                    source_goal_id=source_id,
                    mode="unify",
                )
            if mode == "equal":
                if state.constraints.satisfied_literals(
                    source_literal,
                    left_instance=source_instance,
                    right=target_literal,
                    right_instance=target_instance,
                    logic=state.problem.logic,
                    domain=state.problem.domain,
                ):
                    return Factorization(source_id, mode="equal")
                return None
            delta = state.constraints.delta_for_literals(
                older=source_literal,
                older_instance=source_instance,
                newer=target_literal,
                newer_instance=target_instance,
                logic=state.problem.logic,
                domain=state.problem.domain,
            )
            if delta is None:
                return None
            return Factorization(
                source_goal_id=source_id,
                mode="unify",
                constraint_delta=delta,
            )

        return Dynamics._source_rules_for(
            state,
            literal=literal,
            literal_instance=literal_instance,
            source_ids=sources,
            make_rule=make_rule,
        )

    @staticmethod
    def reduction_rules_for(state: State, goal_id: int) -> tuple[Reduction, ...]:
        target_context = state.literal_context_at(goal_id)
        if target_context is None:
            return ()
        literal, literal_instance = target_context
        sources = state.path_goal_ids_for(goal_id, literal.complement_symbol)
        if not sources:
            return ()

        def make_rule(
            source_id: int,
            source_literal: Literal,
            source_instance: int | None,
            target_literal: Literal,
            target_instance: int | None,
        ) -> Reduction | None:
            if (
                state.problem.logic == "classical"
                and source_literal.is_ground
                and target_literal.is_ground
            ):
                if source_literal.atom == target_literal.atom:
                    return Reduction(source_id)
                return None
            delta = state.constraints.delta_for_literals(
                older=source_literal,
                older_instance=source_instance,
                newer=target_literal,
                newer_instance=target_instance,
                logic=state.problem.logic,
                domain=state.problem.domain,
            )
            if delta is None:
                return None
            return Reduction(source_id, delta)

        return Dynamics._source_rules_for(
            state,
            literal=literal,
            literal_instance=literal_instance,
            source_ids=sources,
            make_rule=make_rule,
        )

    @staticmethod
    def extension_rules_for(state: State, goal_id: int) -> tuple[Extension, ...]:
        target_context = state.literal_context_at(goal_id)
        if target_context is None:
            return ()
        goal = state.tableau.goals[goal_id]
        if goal.clause_idx is None or goal.literal_index is None:
            return ()
        cache = goal.extension_cache
        target_gate = (state.constraints.revision, target_context[0])
        cached_rules = cache.current_rules(target_gate)
        if cached_rules is not None:
            return cached_rules  # type: ignore[return-value]
        keys = state.problem.matrix.complements(goal.clause_idx, goal.literal_index)
        rules: list[Extension] = []
        for clause_idx, lit_idx in keys:
            instance_id = state.fresh_instance_id()
            action = Dynamics.extension_action_for_position(
                state,
                goal_id,
                clause_idx,
                lit_idx,
                instance_id=instance_id,
            )
            if action is not None:
                rules.append(action.rule)
        result = tuple(rules)
        cache.replace(target_gate, result)
        return result

    @staticmethod
    def extension_action_for_position(
        state: State,
        goal_id: int,
        clause_idx: int,
        lit_idx: int,
        *,
        instance_id: int,
    ) -> ApplyAction[Extension] | None:
        target_context = state.literal_context_at(goal_id)
        if target_context is None:
            return None
        literal, literal_instance = target_context
        clause = state.problem.matrix.clauses[clause_idx]
        selected_literal = clause.literal(lit_idx)
        free_variables = (
            ()
            if not clause.free_variables
            else Dynamics._free_variable_refs(clause, instance_id)
        )
        if (
            state.problem.logic == "classical"
            and literal.is_ground
            and selected_literal.is_ground
        ):
            if literal.atom != selected_literal.atom:
                return None
            delta = state.constraints.delta_for_free_variables(
                free_variables,
                logic=state.problem.logic,
                domain=state.problem.domain,
            )
            if delta is None:
                return None
            return ApplyAction(
                goal_id,
                Extension(
                    lit_idx=lit_idx,
                    clause=clause,
                    constraint_delta=delta,
                    clause_idx=clause_idx,
                    instance_id=instance_id,
                ),
            )
        delta = state.constraints.delta_for_literals(
            older=literal,
            older_instance=literal_instance,
            newer=selected_literal,
            newer_instance=instance_id,
            logic=state.problem.logic,
            domain=state.problem.domain,
            free_variables=free_variables,
        )
        if delta is None:
            return None
        return ApplyAction(
            goal_id,
            Extension(
                lit_idx=lit_idx,
                clause=clause,
                constraint_delta=delta,
                clause_idx=clause_idx,
                instance_id=instance_id,
            ),
        )

    @staticmethod
    def extension_terms_unify_for_position(
        state: State,
        goal_id: int,
        clause_idx: int,
        lit_idx: int,
        *,
        instance_id: int,
    ) -> bool:
        target_context = state.literal_context_at(goal_id)
        if target_context is None:
            return False
        target_literal, target_instance = target_context
        selected_literal = state.problem.matrix.clauses[clause_idx].literal(lit_idx)
        if (
            state.problem.logic == "classical"
            and target_literal.is_ground
            and selected_literal.is_ground
        ):
            return target_literal.atom == selected_literal.atom
        unifies, _ = state.constraints.terms.unify_literals(
            older=target_literal,
            older_instance=target_instance,
            newer=selected_literal,
            newer_instance=instance_id,
        )
        return unifies

    @staticmethod
    def extension_candidate_positions_for(
        state: State,
        goal_id: int,
    ) -> tuple[tuple[int, int], ...]:
        if state.literal_context_at(goal_id) is None:
            return ()
        goal = state.tableau.goals[goal_id]
        if goal.clause_idx is None or goal.literal_index is None:
            return ()
        return state.problem.matrix.complements(goal.clause_idx, goal.literal_index)

    @staticmethod
    def extension_term_candidate_positions_for(
        state: State,
        goal_id: int,
    ) -> tuple[tuple[int, int], ...]:
        target_context = state.literal_context_at(goal_id)
        if target_context is None:
            return ()
        target_literal, target_instance = target_context
        goal = state.tableau.goals[goal_id]
        if goal.clause_idx is None or goal.literal_index is None:
            return ()

        candidates: list[tuple[int, int]] = []
        for clause_idx, lit_idx in state.problem.matrix.complements(
            goal.clause_idx,
            goal.literal_index,
        ):
            selected_literal = state.problem.matrix.clauses[clause_idx].literal(lit_idx)
            unifies, _ = state.constraints.terms.unify_literals(
                older=target_literal,
                older_instance=target_instance,
                newer=selected_literal,
                newer_instance=_synthetic_extension_instance_id(clause_idx, lit_idx),
            )
            if unifies:
                candidates.append((clause_idx, lit_idx))
        return tuple(candidates)

    @staticmethod
    def is_regular(state: State, goal: TableauNode) -> bool:
        return Dynamics.regularity_violation(state, goal) is None

    @staticmethod
    def regularity_violation(
        state: State, goal: TableauNode
    ) -> tuple[Literal, Literal] | None:
        if goal.parent_rule_application_id is None:
            return None
        app = state.tableau.rule_applications[goal.parent_rule_application_id]
        if not isinstance(app.rule, Extension):
            return None
        for child_goal_id in app.child_goal_ids:
            child_goal = state.tableau.goals[child_goal_id]
            if child_goal.closed:
                continue
            clause_literal = state.source_literal_at(child_goal_id)
            if clause_literal is None:
                continue
            path_goal_ids = state.path_goal_ids_for(
                goal.goal_id, clause_literal.signed_symbol
            )
            if not path_goal_ids:
                continue
            for path_goal_id in path_goal_ids:
                path_literal = state.source_literal_at(path_goal_id)
                if path_literal is None:
                    continue
                if (
                    state.problem.logic == "classical"
                    and clause_literal.is_ground
                    and path_literal.is_ground
                ):
                    if clause_literal.atom == path_literal.atom:
                        return clause_literal, path_literal
                    continue
                if state.constraints.satisfied_literals(
                    clause_literal,
                    left_instance=child_goal.instance_id,
                    right=path_literal,
                    right_instance=state.tableau.goals[path_goal_id].instance_id,
                    logic=state.problem.logic,
                    domain=state.problem.domain,
                ):
                    return clause_literal, path_literal
        return None

    @staticmethod
    def get_undo(_state: State, goal: TableauNode) -> UndoAction | None:
        return (
            None
            if goal.applied_rule_application_id is None
            else UndoAction(goal.applied_rule_application_id)
        )

    @staticmethod
    def transition(state: State, action: Action | None) -> State:
        """Apply a policy-selected action.

        This is intentionally garbage-in, garbage-out. Policies select actions
        from the current action space and must only undo active rule
        applications.
        """
        if action is None:
            return state
        if isinstance(action, ApplyAction):
            state.apply_rule(
                parent_goal_id=action.goal_id,
                rule=action.rule,
            )
            return state
        state.undo_rule_application(action.step_id)
        return state

    @staticmethod
    def _apply_actions(
        goal_id: int, rules: tuple[RuleT, ...]
    ) -> tuple[ApplyAction[RuleT], ...]:
        return tuple(ApplyAction(goal_id, rule) for rule in rules)

    @staticmethod
    def _source_rules_for(
        state: State,
        *,
        literal: Literal,
        literal_instance: int | None,
        source_ids: tuple[int, ...],
        make_rule: Callable[
            [int, Literal, int | None, Literal, int | None], RuleT | None
        ],
    ) -> tuple[RuleT, ...]:
        rules: list[RuleT] = []
        for source_id in source_ids:
            source_context = state.literal_context_at(source_id)
            if source_context is None:
                continue
            source_literal, source_instance = source_context
            rule = make_rule(
                source_id,
                source_literal,
                source_instance,
                literal,
                literal_instance,
            )
            if rule is not None:
                rules.append(rule)
        return tuple(rules)

    @staticmethod
    def _free_variable_refs(
        clause: Clause,
        instance_id: int | None,
    ) -> tuple[FreeVariableReference, ...]:
        return tuple((variable, instance_id) for variable in clause.free_variables)


def _synthetic_extension_instance_id(clause_idx: int, lit_idx: int) -> int:
    return -((clause_idx + 1) * 100_000 + lit_idx + 1)


__all__ = [
    "Dynamics",
]
