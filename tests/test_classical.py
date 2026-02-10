from connections.logic.syntax import Literal, Matrix
from connections.search.state import State
from connections.search.env import ConnectionEnv, Settings


def test_classical_initial_state():
    env = ConnectionEnv("tests/cnf_problems/SYN081+1.cnf")
    assert isinstance(env.state, State)
    assert isinstance(env.state.matrix, Matrix)
    assert env.action_space
    assert env.action_space[0] is not None


def test_classical_first_step_sets_goal_literal():
    env = ConnectionEnv("tests/cnf_problems/SYN081+1.cnf")
    state, reward, done, info = env.step(env.action_space[0])
    assert isinstance(state.goal.literal, Literal)
    assert reward in (0, 1)
    assert "status" in info
    assert done is state.is_terminal


def test_classical_runs_multiple_steps_without_crash():
    env = ConnectionEnv(
        "tests/cnf_problems/SET718+4.p",
        settings=Settings(iterative_deepening=False),
    )
    state = env.state
    for _ in range(50):
        action = env.action_space[0]
        state, _, done, _ = env.step(action)
        if done:
            break
    assert state is env.state
