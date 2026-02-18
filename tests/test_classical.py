from connections.logic.syntax import Literal, Matrix
from connections.search.actions import Action
from connections.search.state import State
from connections.search.env import ConnectionEnv, Settings


def test_classical_initial_state():
    env = ConnectionEnv("tests/cnf_problems/SYN081+1.cnf")
    assert isinstance(env.state, State)
    assert isinstance(env.state.matrix, Matrix)
    assert env.action_space
    first_goal_actions = next(iter(env.action_space.values()))
    assert first_goal_actions


def test_classical_first_step_sets_goal_literal():
    env = ConnectionEnv("tests/cnf_problems/SYN081+1.cnf")
    first_goal_actions = next(iter(env.action_space.values()))
    action = next(iter(first_goal_actions.values()))
    state, reward, done, info = env.step(action)
    if not done:
        assert env.fringe_node_ids
        first_goal = next(iter(env.fringe_node_ids))
        assert isinstance(env.state.tableau.get_node(first_goal).literal, Literal)
    assert reward in (0, 1)
    assert "status" in info
    assert done is state.is_terminal


def test_classical_runs_multiple_steps_without_crash():
    env = ConnectionEnv("tests/cnf_problems/SET718+4.p", settings=Settings())
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


def test_serialized_observation_and_action_roundtrip():
    env = ConnectionEnv("tests/cnf_problems/SYN081+1.cnf")
    observation = env.observation
    assert "available_actions_by_goal" in observation
    goal_id = next(iter(observation["available_actions_by_goal"]))
    action_id = next(iter(observation["available_actions_by_goal"][goal_id]))
    action_payload = observation["available_actions_by_goal"][goal_id][action_id]

    state, _, _, info = env.step(action_payload)
    assert isinstance(state, State)
    assert "status" in info

    action = Action.from_dict(action_payload)
    assert action.id == action_id
