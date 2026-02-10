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
    assert env.action_space[0] is not None


def test_intuitionistic_first_step_sets_goal_literal():
    env = ConnectionEnv(
        "tests/icnf_problems/SYN081+1.cnf",
        settings=Settings(logic="intuitionistic"),
    )
    state, reward, done, info = env.step(env.action_space[0])
    if not done:
        assert isinstance(state.goal.literal, Literal)
    assert reward in (0, 1)
    assert "status" in info
    assert done is state.is_terminal


def test_intuitionistic_runs_multiple_steps_without_crash():
    env = ConnectionEnv(
        "tests/icnf_problems/SWV230+1.p",
        settings=Settings(logic="intuitionistic", iterative_deepening=True),
    )
    state = env.state
    for _ in range(50):
        action = env.action_space[0]
        state, _, done, _ = env.step(action)
        if done:
            break
    assert state is env.state
