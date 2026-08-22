from __future__ import annotations

from connections.syntax.formula import Atom
from connections.syntax.matrix import Clause, Literal, Matrix
from connections.agent import AgentOptions, AgentStatus, OnlineDFSAgent


from connections.calculus.actions import ApplyAction, UndoAction
from connections.calculus.dynamics import Dynamics
from connections.calculus.rules import Start
from connections.calculus.state import State
from connections.calculus.tableau import Tableau

def _choose_first(state, actions):
    _ = state
    return actions[0]


def _lit(name: str, *, neg: bool = False) -> Literal:
    return Literal(atom=Atom(name), polarity=not neg)


def _state(matrix: Matrix) -> State:
    return State(matrix=matrix,
        tableau=Tableau(),
    )


def _second(state, actions):
    _ = state
    return actions[1]


def _second_agent(**options):
    return OnlineDFSAgent(_second, AgentOptions(**options))


def _first_agent(**options):
    return OnlineDFSAgent(_choose_first, AgentOptions(**options))


def test_dfs_policy_delegates_action_ordering() -> None:
    state = _state(
        Matrix(
            (
                Clause((_lit("p"),)),
                Clause((_lit("q"),)),
            )
        )
    )

    action = _second_agent()(state)

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

    action = _first_agent()(state)

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
    policy = _first_agent()

    start = policy(state)
    assert isinstance(start, ApplyAction)
    Dynamics.transition(state, start)
    action = policy(state)

    assert isinstance(action, UndoAction)


def test_dfs_policy_returns_non_theorem_after_root_exhaustion() -> None:
    state = _state(Matrix((Clause((_lit("p"),)),)))
    policy = _first_agent()

    start = policy(state)
    assert isinstance(start, ApplyAction)
    Dynamics.transition(state, start)
    undo = policy(state)

    assert isinstance(undo, UndoAction)
    Dynamics.transition(state, undo)
    assert policy(state) is None
    assert policy.status is AgentStatus.DFS_EXHAUSTED
