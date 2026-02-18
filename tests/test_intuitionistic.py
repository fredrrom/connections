from connections.logic.syntax import Literal, Matrix
from connections.search.state import State
from connections.search.env import ConnectionEnv, Settings


def test_intuitionistic_initial_state():
    env = ConnectionEnv(
        "tests/icnf_problems/SYN081+1.cnf",
        settings=Settings(logic="intuitionistic"),
    )
    assert isinstance(env.state, State)
    assert isinstance(env.state.matrix, Matrix)
    assert env.action_space
    first_goal_actions = next(iter(env.action_space.values()))
    assert first_goal_actions


def test_intuitionistic_first_step_sets_goal_literal():
    env = ConnectionEnv(
        "tests/icnf_problems/SYN081+1.cnf",
        settings=Settings(logic="intuitionistic"),
    )
    first_goal_actions = next(iter(env.action_space.values()))
    action = next(iter(first_goal_actions.values()))
    state, reward, done, info = env.step(action)
    if not done:
        first_goal = next(iter(env.fringe_node_ids))
        assert isinstance(env.state.tableau.get_node(first_goal).literal, Literal)
    assert reward in (0, 1)
    assert "status" in info
    assert done is state.is_terminal


def test_intuitionistic_runs_multiple_steps_without_crash():
    env = ConnectionEnv(
        "tests/icnf_problems/SWV230+1.p",
        settings=Settings(logic="intuitionistic"),
    )
    state = env.state
    for _ in range(50):
        if not env.action_space:
            break
        first_goal_actions = next(iter(env.action_space.values()))
        action = next(iter(first_goal_actions.values()))
        state, _, done, _ = env.step(action)
        if done:
            break
    assert state is env.state
