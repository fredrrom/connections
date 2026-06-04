from __future__ import annotations

from connections.core.formula import Atom
from connections.core.matrix import Clause, Literal, Matrix
from connections.core.status import ProverOutcome
from connections.policy import DFSPolicy
from connections.prover.actions import ActionChoice, ApplyAction, UndoAction
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


def _action(output):
    if isinstance(output, ActionChoice):
        return output.action
    return output


class _SecondActionPolicy(DFSPolicy):
    def next_action(self, state, actions):
        return self.choose(actions, 1)


def test_dfs_policy_delegates_action_ordering() -> None:
    state = _state(
        Matrix(
            (
                Clause((_lit("p"),)),
                Clause((_lit("q"),)),
            )
        )
    )

    action = _action(_SecondActionPolicy()(state))

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

    action = _action(DFSPolicy()(state))

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
    policy = DFSPolicy()

    start = _action(policy(state))
    Dynamics.transition(state, start)
    action = _action(policy(state))

    assert isinstance(action, UndoAction)


def test_dfs_policy_returns_non_theorem_after_root_exhaustion() -> None:
    state = _state(Matrix((Clause((_lit("p"),)),)))
    policy = DFSPolicy()

    start = _action(policy(state))
    Dynamics.transition(state, start)
    undo = _action(policy(state))

    assert isinstance(undo, UndoAction)
    Dynamics.transition(state, undo)
    assert policy(state) is ProverOutcome.DFS_EXHAUSTED
