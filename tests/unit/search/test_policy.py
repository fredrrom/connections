from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from connections.clausification import matrix_from_file
from connections.core.formula import Atom, Variable
from connections.core.matrix import Clause, Literal, Matrix
from connections.core.status import ProverOutcome
import connections.policy.dfs as policy_module
import connections.policy.id as id_policy_module
from connections.policy import (
    DFSPolicy,
    IterativeDeepeningPolicy,
)
from connections.prover.actions import (
    Action,
    ActionChoice,
    AnyApplyAction,
    ApplyAction,
    ApplyActions,
    UndoAction,
)
from connections.prover.dynamics import Dynamics
from connections.pycop.policy import PycopPolicy
from connections.prover.prover import Problem
from connections.prover.rules import Extension, Factorization, Reduction, Start
from connections.prover.state import State
from connections.prover.tableau import Tableau
from connections.trace_logging import TRACE_LEVEL


def _lit(label: str) -> Literal:
    return Literal(atom=Atom(label))


_DUMMY_PROBLEM = Problem(
    matrix=Matrix((Clause((_lit("dummy"),)),)), start_clauses="positive"
)


def _apply(kind: str, token: int, goal_id: int) -> AnyApplyAction:
    if kind == "start":
        return ApplyAction(goal_id=goal_id, rule=Start(Clause((_lit(f"st{token}"),))))
    if kind == "extension":
        return ApplyAction(
            goal_id=goal_id,
            rule=Extension(lit_idx=0, clause=Clause((_lit(f"ex{token}"),))),
        )
    if kind == "reduction":
        return ApplyAction(goal_id=goal_id, rule=Reduction(source_goal_id=token))
    if kind == "factorization":
        return ApplyAction(goal_id=goal_id, rule=Factorization(source_goal_id=token))
    raise ValueError(kind)


@dataclass
class _FakeGoal:
    goal_id: int
    depth: int
    introduced_by_rule_application_id: int | None
    applied_rule_application_id: int | None = None
    closed: bool = False


@dataclass
class _FakeStep:
    rule_application_id: int
    parent_goal_id: int
    child_goal_ids: tuple[int, ...] = ()


@dataclass
class _FakeTableau:
    goals: dict[int, _FakeGoal] | None = None
    rule_applications: dict[int, _FakeStep] | None = None
    root_goal_id: int = 0

    @property
    def root(self) -> _FakeGoal:
        assert self.goals is not None
        return next(iter(self.goals.values()))


class _FakeActionSpace:
    def __init__(
        self,
        tableau: _FakeTableau,
        goals: list[tuple[_FakeGoal, list[AnyApplyAction]]],
        rule_applications: list[tuple[int, int, str]],
    ):
        self.tableau = tableau
        self._goal_ids = tuple(goal.goal_id for goal, _ in goals)
        self._goal_actions = {goal.goal_id: tuple(actions) for goal, actions in goals}
        tableau.goals = {
            **(tableau.goals or {}),
            **{goal.goal_id: goal for goal, _ in goals},
        }
        tableau.rule_applications = {
            **(tableau.rule_applications or {}),
            **{
                rule_application_id: _FakeStep(rule_application_id, parent_goal_id)
                for rule_application_id, parent_goal_id, _ in rule_applications
            },
        }
        self._rule_application_ids = tuple(
            rule_application_id for rule_application_id, _, _ in rule_applications
        )
        self._undo_labels = {
            rule_application_id: label
            for rule_application_id, _, label in rule_applications
        }

    def rule_application_ids(self, _state: State) -> tuple[int, ...]:
        return self._rule_application_ids

    def goals(self, _state: State) -> tuple[_FakeGoal, ...]:
        assert self.tableau.goals is not None
        return tuple(self.tableau.goals[goal_id] for goal_id in self._goal_ids)

    def get_apply(self, _state: State, goal: _FakeGoal) -> ApplyActions:
        actions = self._goal_actions.get(goal.goal_id, ())
        starts = tuple(action for action in actions if isinstance(action.rule, Start))
        factorizations = tuple(
            action for action in actions if isinstance(action.rule, Factorization)
        )
        reductions = tuple(
            action for action in actions if isinstance(action.rule, Reduction)
        )
        extensions = tuple(
            action for action in actions if isinstance(action.rule, Extension)
        )
        return ApplyActions(
            start=cast(tuple[ApplyAction[Start], ...], starts),
            factorization=cast(tuple[ApplyAction[Factorization], ...], factorizations),
            reduction=cast(tuple[ApplyAction[Reduction], ...], reductions),
            extension=cast(tuple[ApplyAction[Extension], ...], extensions),
        )

    def get_undo(self, _state: State, goal: _FakeGoal) -> UndoAction | None:
        if goal.applied_rule_application_id is None:
            return None
        return UndoAction(step_id=goal.applied_rule_application_id)

    def label(self, action: Action) -> str:
        if isinstance(action, UndoAction):
            return self._undo_labels[action.step_id]

        rule = action.rule
        if isinstance(rule, Start):
            return rule.clause.literals[0].atom.symbol
        if isinstance(rule, Extension):
            return rule.clause.literals[0].atom.symbol
        if isinstance(rule, Reduction):
            return f"re{rule.source_goal_id}"
        return f"fa{rule.source_goal_id}"


def _make_state(
    *,
    tableau: _FakeTableau,
    goals: list[tuple[_FakeGoal, list[AnyApplyAction]]],
    rule_applications: list[tuple[int, int, str]] | None = None,
) -> tuple[State, _FakeActionSpace]:
    rule_applications = rule_applications or []
    action_space = _FakeActionSpace(
        tableau, goals=goals, rule_applications=rule_applications
    )
    state = State(
        problem=cast(Any, _DUMMY_PROBLEM),
        tableau=cast(Any, tableau),
    )
    state.fringe = list(action_space.goals(state))
    return state, action_space


def _selected_action(output):
    if isinstance(output, ActionChoice):
        return output.action
    return output


def _label(action_space: _FakeActionSpace, action: object) -> str | None:
    action = _selected_action(action)
    if action is None:
        return None
    return action_space.label(action)


class _DynamicsSwitch:
    def __init__(self, current: _FakeActionSpace):
        self.current = current

    def goals(self, state: State):
        return self.current.goals(state)

    def apply_actions(self, state: State, goal: _FakeGoal, **_kwargs) -> ApplyActions:
        return self.current.get_apply(state, goal)

    def regularity_violation(self, _state: State, _goal: _FakeGoal):
        return None

    def get_undo(self, state: State, goal: _FakeGoal) -> UndoAction | None:
        return self.current.get_undo(state, goal)


def _patch_dynamics(monkeypatch, dynamics: _FakeActionSpace) -> _DynamicsSwitch:
    switch = _DynamicsSwitch(dynamics)
    monkeypatch.setattr(policy_module, "Dynamics", switch)
    if hasattr(id_policy_module, "Dynamics"):
        monkeypatch.setattr(id_policy_module, "Dynamics", switch)
    return switch


def test_dfs_policy_selects_first_available_action(monkeypatch):
    goal = _FakeGoal(goal_id=1, depth=1, introduced_by_rule_application_id=10)
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                goal,
                [
                    _apply("extension", 0, goal.goal_id),
                    _apply("extension", 1, goal.goal_id),
                ],
            )
        ],
    )

    _patch_dynamics(monkeypatch, dynamics)
    action = DFSPolicy()(state)

    assert _label(dynamics, action) == "ex0"


def test_dfs_policy_with_scut_only_tries_first_start_clause(monkeypatch):
    root_goal = _FakeGoal(goal_id=0, depth=-1, introduced_by_rule_application_id=None)
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                root_goal,
                [
                    _apply("start", 0, root_goal.goal_id),
                    _apply("start", 1, root_goal.goal_id),
                ],
            )
        ],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = DFSPolicy(scut=True)

    first = policy(state)

    assert _label(dynamics, first) == "st0"
    assert policy(state) is ProverOutcome.DFS_EXHAUSTED


def test_dfs_policy_reads_cut_and_scut_from_constructor_args():
    policy = DFSPolicy(cut=True, scut=True)

    assert policy.cut_enabled is True
    assert policy.scut_enabled is True


def test_dfs_policy_tries_remaining_actions_then_backtracks_ancestor_step(monkeypatch):
    root_goal = _FakeGoal(goal_id=0, depth=-1, introduced_by_rule_application_id=None)
    child_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    child_goal = _FakeGoal(goal_id=1, depth=1, introduced_by_rule_application_id=100)
    root_state, root_dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                root_goal,
                [
                    _apply("start", 0, root_goal.goal_id),
                    _apply("start", 1, root_goal.goal_id),
                ],
            )
        ],
    )
    child_state, child_dynamics = _make_state(
        tableau=_FakeTableau(goals={child_root_goal.goal_id: child_root_goal}),
        goals=[
            (
                child_goal,
                [
                    _apply("extension", 0, child_goal.goal_id),
                    _apply("extension", 1, child_goal.goal_id),
                ],
            )
        ],
        rule_applications=[(100, child_root_goal.goal_id, "bt_root")],
    )
    child_tableau = cast(_FakeTableau, child_state.tableau)
    assert (
        child_tableau.goals is not None and child_tableau.rule_applications is not None
    )
    child_tableau.goals[child_root_goal.goal_id].applied_rule_application_id = 100
    child_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    dynamics_switch = _patch_dynamics(monkeypatch, root_dynamics)
    policy = DFSPolicy()

    first = policy(root_state)
    dynamics_switch.current = child_dynamics
    second = policy(child_state)
    third = policy(child_state)
    fourth = policy(child_state)
    labels = [
        _label(root_dynamics, first),
        _label(child_dynamics, second),
        _label(child_dynamics, third),
        _label(child_dynamics, fourth),
    ]

    assert labels == ["st0", "ex0", "ex1", "bt_root"]


def test_dfs_policy_backtracks_highest_exhausted_subtree(monkeypatch):
    root_goal = _FakeGoal(goal_id=0, depth=-1, introduced_by_rule_application_id=None)
    child_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    child_goal = _FakeGoal(goal_id=1, depth=0, introduced_by_rule_application_id=100)
    leaf_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    leaf_child_goal = _FakeGoal(
        goal_id=1, depth=0, introduced_by_rule_application_id=100
    )
    leaf_goal = _FakeGoal(goal_id=2, depth=1, introduced_by_rule_application_id=200)
    root_state, root_dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                root_goal,
                [
                    _apply("start", 0, root_goal.goal_id),
                    _apply("start", 1, root_goal.goal_id),
                ],
            )
        ],
    )
    child_state, child_dynamics = _make_state(
        tableau=_FakeTableau(goals={child_root_goal.goal_id: child_root_goal}),
        goals=[(child_goal, [_apply("extension", 0, child_goal.goal_id)])],
        rule_applications=[(100, child_root_goal.goal_id, "bt_root")],
    )
    child_tableau = cast(_FakeTableau, child_state.tableau)
    assert (
        child_tableau.goals is not None and child_tableau.rule_applications is not None
    )
    child_tableau.goals[child_root_goal.goal_id].applied_rule_application_id = 100
    child_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    leaf_state, leaf_dynamics = _make_state(
        tableau=_FakeTableau(
            goals={
                leaf_root_goal.goal_id: leaf_root_goal,
                leaf_child_goal.goal_id: leaf_child_goal,
            }
        ),
        goals=[(leaf_goal, [])],
        rule_applications=[
            (100, leaf_root_goal.goal_id, "bt_root"),
            (200, leaf_child_goal.goal_id, "bt_child"),
        ],
    )
    leaf_tableau = cast(_FakeTableau, leaf_state.tableau)
    assert leaf_tableau.goals is not None and leaf_tableau.rule_applications is not None
    leaf_tableau.goals[leaf_root_goal.goal_id].applied_rule_application_id = 100
    leaf_tableau.goals[leaf_child_goal.goal_id].applied_rule_application_id = 200
    leaf_tableau.rule_applications[100].child_goal_ids = (leaf_child_goal.goal_id,)
    leaf_tableau.rule_applications[200].child_goal_ids = (leaf_goal.goal_id,)
    dynamics_switch = _patch_dynamics(monkeypatch, root_dynamics)
    policy = DFSPolicy(backtrack="maximal")

    first = policy(root_state)
    dynamics_switch.current = child_dynamics
    second = policy(child_state)
    dynamics_switch.current = leaf_dynamics
    third = policy(leaf_state)

    assert _label(root_dynamics, first) == "st0"
    assert _label(child_dynamics, second) == "ex0"
    assert _label(leaf_dynamics, third) == "bt_root"


def test_dfs_policy_step_backtracking_keeps_nearest_exhausted_step(monkeypatch):
    root_goal = _FakeGoal(goal_id=0, depth=-1, introduced_by_rule_application_id=None)
    child_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    child_goal = _FakeGoal(goal_id=1, depth=0, introduced_by_rule_application_id=100)
    leaf_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    leaf_child_goal = _FakeGoal(
        goal_id=1, depth=0, introduced_by_rule_application_id=100
    )
    leaf_goal = _FakeGoal(goal_id=2, depth=1, introduced_by_rule_application_id=200)
    root_state, root_dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                root_goal,
                [
                    _apply("start", 0, root_goal.goal_id),
                    _apply("start", 1, root_goal.goal_id),
                ],
            )
        ],
    )
    child_state, child_dynamics = _make_state(
        tableau=_FakeTableau(goals={child_root_goal.goal_id: child_root_goal}),
        goals=[(child_goal, [_apply("extension", 0, child_goal.goal_id)])],
        rule_applications=[(100, child_root_goal.goal_id, "bt_root")],
    )
    child_tableau = cast(_FakeTableau, child_state.tableau)
    assert (
        child_tableau.goals is not None and child_tableau.rule_applications is not None
    )
    child_tableau.goals[child_root_goal.goal_id].applied_rule_application_id = 100
    child_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    leaf_state, leaf_dynamics = _make_state(
        tableau=_FakeTableau(
            goals={
                leaf_root_goal.goal_id: leaf_root_goal,
                leaf_child_goal.goal_id: leaf_child_goal,
            }
        ),
        goals=[(leaf_goal, [])],
        rule_applications=[
            (100, leaf_root_goal.goal_id, "bt_root"),
            (200, leaf_child_goal.goal_id, "bt_child"),
        ],
    )
    leaf_tableau = cast(_FakeTableau, leaf_state.tableau)
    assert leaf_tableau.goals is not None and leaf_tableau.rule_applications is not None
    leaf_tableau.goals[leaf_root_goal.goal_id].applied_rule_application_id = 100
    leaf_tableau.goals[leaf_child_goal.goal_id].applied_rule_application_id = 200
    leaf_tableau.rule_applications[100].child_goal_ids = (leaf_child_goal.goal_id,)
    leaf_tableau.rule_applications[200].child_goal_ids = (leaf_goal.goal_id,)
    dynamics_switch = _patch_dynamics(monkeypatch, root_dynamics)
    policy = DFSPolicy(backtrack="step")

    first = policy(root_state)
    dynamics_switch.current = child_dynamics
    second = policy(child_state)
    dynamics_switch.current = leaf_dynamics
    third = policy(leaf_state)

    assert _label(root_dynamics, first) == "st0"
    assert _label(child_dynamics, second) == "ex0"
    assert _label(leaf_dynamics, third) == "bt_child"


def test_dfs_policy_closed_goal_without_cut_backtracks_before_parent_actions(
    monkeypatch,
):
    root_goal = _FakeGoal(goal_id=0, depth=-1, introduced_by_rule_application_id=None)
    child_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    solved_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    child_goal = _FakeGoal(goal_id=1, depth=1, introduced_by_rule_application_id=100)
    root_state, root_dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                root_goal,
                [
                    _apply("start", 0, root_goal.goal_id),
                    _apply("start", 1, root_goal.goal_id),
                ],
            )
        ],
    )
    child_state, child_dynamics = _make_state(
        tableau=_FakeTableau(goals={child_root_goal.goal_id: child_root_goal}),
        goals=[
            (
                child_goal,
                [
                    _apply("extension", 0, child_goal.goal_id),
                    _apply("extension", 1, child_goal.goal_id),
                ],
            )
        ],
        rule_applications=[(100, child_root_goal.goal_id, "bt_root")],
    )
    child_tableau = cast(_FakeTableau, child_state.tableau)
    assert (
        child_tableau.goals is not None and child_tableau.rule_applications is not None
    )
    child_tableau.goals[child_root_goal.goal_id].applied_rule_application_id = 100
    child_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    solved_state, solved_dynamics = _make_state(
        tableau=_FakeTableau(
            goals={
                solved_root_goal.goal_id: solved_root_goal,
                child_goal.goal_id: _FakeGoal(
                    goal_id=child_goal.goal_id,
                    depth=1,
                    introduced_by_rule_application_id=100,
                    closed=True,
                ),
            }
        ),
        goals=[(solved_root_goal, [_apply("start", 1, solved_root_goal.goal_id)])],
        rule_applications=[(100, solved_root_goal.goal_id, "bt_root")],
    )
    solved_tableau = cast(_FakeTableau, solved_state.tableau)
    assert (
        solved_tableau.goals is not None
        and solved_tableau.rule_applications is not None
    )
    solved_tableau.goals[solved_root_goal.goal_id].applied_rule_application_id = 100
    solved_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    dynamics_switch = _patch_dynamics(monkeypatch, root_dynamics)
    policy = DFSPolicy()

    assert _label(root_dynamics, policy(root_state)) == "st0"
    dynamics_switch.current = child_dynamics
    assert _label(child_dynamics, policy(child_state)) == "ex0"
    dynamics_switch.current = solved_dynamics
    assert _label(solved_dynamics, policy(solved_state)) == "bt_root"


def test_dfs_policy_cut_returns_undo_before_remaining_child_actions(monkeypatch):
    root_goal = _FakeGoal(goal_id=0, depth=-1, introduced_by_rule_application_id=None)
    child_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    solved_root_goal = _FakeGoal(
        goal_id=0, depth=-1, introduced_by_rule_application_id=None
    )
    child_goal = _FakeGoal(goal_id=1, depth=1, introduced_by_rule_application_id=100)
    root_state, root_dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                root_goal,
                [
                    _apply("start", 0, root_goal.goal_id),
                    _apply("start", 1, root_goal.goal_id),
                ],
            )
        ],
    )
    child_state, child_dynamics = _make_state(
        tableau=_FakeTableau(goals={child_root_goal.goal_id: child_root_goal}),
        goals=[
            (
                child_goal,
                [
                    _apply("extension", 0, child_goal.goal_id),
                    _apply("extension", 1, child_goal.goal_id),
                ],
            )
        ],
        rule_applications=[(100, child_root_goal.goal_id, "bt_root")],
    )
    child_tableau = cast(_FakeTableau, child_state.tableau)
    assert (
        child_tableau.goals is not None and child_tableau.rule_applications is not None
    )
    child_tableau.goals[child_root_goal.goal_id].applied_rule_application_id = 100
    child_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    solved_state, solved_dynamics = _make_state(
        tableau=_FakeTableau(
            goals={
                solved_root_goal.goal_id: solved_root_goal,
                child_goal.goal_id: _FakeGoal(
                    goal_id=child_goal.goal_id,
                    depth=1,
                    introduced_by_rule_application_id=100,
                    closed=True,
                ),
            }
        ),
        goals=[(solved_root_goal, [_apply("start", 1, solved_root_goal.goal_id)])],
        rule_applications=[(100, solved_root_goal.goal_id, "bt_root")],
    )
    solved_tableau = cast(_FakeTableau, solved_state.tableau)
    assert (
        solved_tableau.goals is not None
        and solved_tableau.rule_applications is not None
    )
    solved_tableau.goals[solved_root_goal.goal_id].applied_rule_application_id = 100
    solved_tableau.rule_applications[100].child_goal_ids = (child_goal.goal_id,)
    dynamics_switch = _patch_dynamics(monkeypatch, root_dynamics)
    policy = DFSPolicy(cut=True)

    assert _label(root_dynamics, policy(root_state)) == "st0"
    dynamics_switch.current = child_dynamics
    assert _label(child_dynamics, policy(child_state)) == "ex0"
    dynamics_switch.current = solved_dynamics
    assert _label(solved_dynamics, policy(solved_state)) == "bt_root"


def test_undo_action_targets_structural_proof_step():
    action = UndoAction(step_id=7)

    assert action.step_id == 7


def test_iterative_deepening_policy_at_depth_limit_prefers_factorization_and_reduction(
    monkeypatch,
):
    goal = _FakeGoal(goal_id=1, depth=1, introduced_by_rule_application_id=10)
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[
            (
                goal,
                [
                    _apply("extension", 0, goal.goal_id),
                    _apply("reduction", 0, goal.goal_id),
                    _apply("factorization", 0, goal.goal_id),
                ],
            )
        ],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy()
    policy.depth_limit = 1

    first = policy(state)
    second = policy(state)

    assert _label(dynamics, first) == "fa0"
    assert _label(dynamics, second) == "re0"


def test_iterative_deepening_logs_path_limit_before_ground_extension(
    monkeypatch, caplog
):
    goal = _FakeGoal(goal_id=1, depth=2, introduced_by_rule_application_id=10)
    ground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(lit_idx=0, clause=Clause((_lit("ground"),))),
    )
    nonground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(
            lit_idx=0,
            clause=Clause((Literal(atom=Atom("nonground", (Variable("X"),))),)),
        ),
    )
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[(goal, [nonground_extension, ground_extension])],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy()
    policy.depth_limit = 0

    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    first = policy(state)

    assert _selected_action(first) == ground_extension
    assert caplog.messages == [
        "pathlim_hit",
    ]


def test_iterative_deepening_does_not_log_path_limit_after_chosen_extension(
    monkeypatch, caplog
):
    goal = _FakeGoal(goal_id=1, depth=2, introduced_by_rule_application_id=10)
    ground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(lit_idx=0, clause=Clause((_lit("ground"),))),
    )
    nonground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(
            lit_idx=0,
            clause=Clause((Literal(atom=Atom("nonground", (Variable("X"),))),)),
        ),
    )
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[(goal, [ground_extension, nonground_extension])],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy()
    policy.depth_limit = 0

    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    first = policy(state)

    assert _selected_action(first) == ground_extension
    assert caplog.messages == []


def test_iterative_deepening_increments_depth_when_frame_stack_is_empty(monkeypatch):
    goal = _FakeGoal(goal_id=1, depth=0, introduced_by_rule_application_id=None)
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[(goal, [_apply("extension", 0, goal.goal_id)])],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy()

    assert policy.depth_limit == 0
    assert _label(dynamics, policy(state)) == "ex0"
    assert policy.depth_limit == 1


def test_iterative_deepening_uses_configured_initial_depth(monkeypatch):
    goal = _FakeGoal(goal_id=1, depth=1, introduced_by_rule_application_id=None)
    nonground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(
            lit_idx=0,
            clause=Clause((Literal(atom=Atom("nonground", (Variable("X"),))),)),
        ),
    )
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[(goal, [nonground_extension])],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy(initial_depth=3)

    assert _selected_action(policy(state)) == nonground_extension
    assert policy.depth_limit == 3


def test_iterative_deepening_rejects_nonpositive_initial_depth():
    with pytest.raises(ValueError, match="at least 1"):
        IterativeDeepeningPolicy(initial_depth=0)


def test_iterative_deepening_counts_root_child_as_path_length_one(monkeypatch, caplog):
    goal = _FakeGoal(goal_id=1, depth=0, introduced_by_rule_application_id=None)
    nonground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(
            lit_idx=0,
            clause=Clause((Literal(atom=Atom("nonground", (Variable("X"),))),)),
        ),
    )
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[(goal, [nonground_extension])],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy()

    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    first = policy(state)

    assert _selected_action(first) == nonground_extension
    assert policy.depth_limit == 2
    assert caplog.messages == [
        "pathlim_hit",
        "pathlim",
    ]


def test_modal_iterative_deepening_traces_rejected_prefix_path_limit_candidate(
    tmp_path, caplog
):
    path = tmp_path / "modal.p"
    path.write_text("qmf(c,conjecture,(#box:p => p)).\n", encoding="utf-8")
    matrix = matrix_from_file(path, logic="D", domain="constant")
    state = State(
        problem=Problem(matrix=matrix, start_clauses="positive", logic="D"),
        tableau=Tableau(),
    )
    policy = IterativeDeepeningPolicy(cut=True, scut=True, comp=7)

    start = _selected_action(policy(state))
    assert isinstance(start, ApplyAction)
    Dynamics.transition(state, start)
    goal_id = state.fringe[0].goal_id
    assert Dynamics.extension_rules_for(state, goal_id) == ()
    assert Dynamics.extension_term_candidate_positions_for(state, goal_id) == ((1, 0),)

    caplog.clear()
    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    action = _selected_action(policy(state))

    assert isinstance(action, UndoAction)
    assert caplog.messages == ["pathlim_hit"]


def test_iterative_deepening_continues_after_comp_with_plain_settings(
    monkeypatch, caplog
):
    goal = _FakeGoal(goal_id=1, depth=0, introduced_by_rule_application_id=None)
    nonground_extension = ApplyAction(
        goal_id=goal.goal_id,
        rule=Extension(
            lit_idx=0,
            clause=Clause((Literal(atom=Atom("nonground", (Variable("X"),))),)),
        ),
    )
    state, dynamics = _make_state(
        tableau=_FakeTableau(),
        goals=[(goal, [nonground_extension])],
    )
    _patch_dynamics(monkeypatch, dynamics)
    policy = IterativeDeepeningPolicy(cut=True, scut=True, comp=1)

    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    first = policy(state)

    assert _selected_action(first) == nonground_extension
    assert policy.depth_limit == 2
    assert policy.comp is None
    assert policy.cut_enabled is False
    assert policy.scut_enabled is False
    assert caplog.messages == [
        "pathlim_hit",
        "pathlim_hit",
        "pathlim",
    ]


def test_pycop_policy_traces_leancop_empty_matrix_choicepoints(caplog):
    state = State(
        problem=Problem(matrix=Matrix(()), start_clauses="positive"),
        tableau=Tableau(),
    )
    policy = PycopPolicy(scut=True, comp=3)

    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    action = policy(state)

    assert action is ProverOutcome.ID_FIXED_POINT
    assert caplog.messages == [
        "scut",
        "start",
        "backtrack",
        "pathlim",
        "scut",
        "start",
        "backtrack",
        "pathlim",
        "scut",
        "start",
        "backtrack",
        "start",
        "backtrack",
    ]


def test_pycop_policy_keeps_real_empty_clause_as_start_action(caplog):
    state = State(
        problem=Problem(matrix=Matrix((Clause(()),)), start_clauses="positive"),
        tableau=Tableau(),
    )
    policy = PycopPolicy(scut=True, comp=3)

    caplog.set_level(TRACE_LEVEL, logger="connections.trace")
    action = policy(state)

    action = _selected_action(action)
    assert isinstance(action, ApplyAction)
    assert isinstance(action.rule, Start)
    assert action.rule.clause.literals == ()
    assert caplog.messages == ["scut"]
