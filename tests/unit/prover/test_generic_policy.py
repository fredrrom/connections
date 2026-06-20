from __future__ import annotations

from connections.syntax.formula import Atom
from connections.syntax.matrix import Clause, Literal, Matrix
from connections.prover.status import ProverOutcome
from connections.policy import DFSPolicy
from connections.prover.actions import ApplyAction, UndoAction
from connections.prover.dynamics import Dynamics
from connections.prover.prover import Problem
from connections.prover.rules import Start
from connections.prover.state import State
from connections.prover.tableau import Tableau


def _lit(name: str, *, neg: bool = False) -> Literal:
    return Literal(atom=Atom(name), polarity=not neg)


def _state(matrix: Matrix) -> State:
    return State(
        problem=Problem(matrix=matrix, start_clauses="positive"),
        tableau=Tableau(),
    )


class _SecondActionPolicy(DFSPolicy):
    def _next_action(self, state, actions):
        _ = state
        return actions[1]


class _ChooseFirstDFSPolicy(DFSPolicy):
    def _next_action(self, state, actions):
        _ = state
        return actions[0]


def test_dfs_policy_delegates_action_ordering() -> None:
    state = _state(
        Matrix(
            (
                Clause((_lit("p"),)),
                Clause((_lit("q"),)),
            )
        )
    )

    action = _SecondActionPolicy()(state)

    assert isinstance(action, ApplyAction)
    assert isinstance(action.rule, Start)
    assert action.rule.clause.literals == (_lit("q"),)


def test_dfs_policy_returns_selected_action() -> None:
    state = _state(
        Matrix(
            (
                Clause((_lit("p"),)),
                Clause((_lit("q"),)),
            )
        )
    )

    action = _ChooseFirstDFSPolicy()(state)

    assert isinstance(action, ApplyAction)
    assert action.goal_id == state.tableau.root_goal_id


def test_dfs_policy_focuses_first_open_sibling_by_default() -> None:
    state = _state(
        Matrix(
            (
                Clause((_lit("p"), _lit("q"))),
                Clause((_lit("q", neg=True),)),
            )
        )
    )
    policy = _ChooseFirstDFSPolicy()

    start = policy(state)
    assert isinstance(start, ApplyAction)
    Dynamics.transition(state, start)
    action = policy(state)

    assert isinstance(action, UndoAction)


def test_dfs_policy_returns_non_theorem_after_root_exhaustion() -> None:
    state = _state(Matrix((Clause((_lit("p"),)),)))
    policy = _ChooseFirstDFSPolicy()

    start = policy(state)
    assert isinstance(start, ApplyAction)
    Dynamics.transition(state, start)
    undo = policy(state)

    assert isinstance(undo, UndoAction)
    Dynamics.transition(state, undo)
    assert policy(state) is ProverOutcome.DFS_EXHAUSTED
