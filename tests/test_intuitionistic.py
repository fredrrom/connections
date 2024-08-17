from connections.env import *
from connections.utils.primitives import *

class TestIntuitionisticState:
    # ARRANGE
    settings = Settings(logic='intuitionistic')
    env = ConnectionEnv('tests/icnf_problems/SYN081+1.cnf', settings=settings)
    state = env.state


    def test_start_states(self):
        action = self.env.action_space[0]

        # ACT
        self.state, reward, done, info = self.env.step(action)
        print(self.state.goal)
        print(self.state.goal.children)
        assert isinstance(self.state.goal.literal, Literal)
        assert str([child.literal for child in self.state.tableau.children]) == '[big_f(_28061), big_f(f(_28061))]'
        assert str(self.state.tableau.children[0].literal) == str(self.state.goal.literal)
        assert self.state.tableau.children[0].children == []
        assert self.state.goal.depth == 0
        assert self.state.tableau.literal is None

    def test_extensions(self):
        # ARRANGE
        neg_lits = self.state.matrix.complements(self.state.goal.literal)

        # ASSERT
        assert str(self.state.goal.literal) == 'big_f(_28061)'
        assert neg_lits == [(0, 1), (2, 0), (2, 1)]
        assert str(self.state._extensions()) == '[ex0: big_f(_28061) -> [big_f(_34365), -big_f(f(_34365))],' \
                                                ' ex1: big_f(_28061) -> [-big_f(f(_28066)), -big_f(_28066)],' \
                                                ' ex2: big_f(_28061) -> [-big_f(f(_28067)), -big_f(_28067)]]'


class TestIConnectionEnv:
    # ARRANGE
    settings = Settings(iterative_deepening=True,
                        logic='intuitionistic')
    env = ConnectionEnv('tests/icnf_problems/SYN081+1.cnf', settings=settings)

    def test_iterative_deepening_steps(self):
        # ARRANGE
        action = self.env.action_space[0]

        # ACT
        observation, reward, done, info = self.env.step(action)
        action = self.env.action_space[0]

        # ACT
        self.state, reward, done, info = self.env.step(action)

        # ASSERT
        assert str(action) == 'ex0: big_f(_28061) -> [big_f(_34362), -big_f(f(_34362))]'
        assert observation.max_depth == 1
        assert observation.goal.depth == 1
        #print(self.env.state.proof_sequence)

        action = self.env.action_space[0]

        # ACT
        self.state, reward, done, info = self.env.step(action)
        assert str(self.env.action_space) == '[ex1: big_f(_28061) -> [-big_f(f(_28063)), -big_f(_28063)],' \
                                             ' ex2: big_f(_28061) -> [-big_f(f(_28064)), -big_f(_28064)],' \
                                             ' Backtrack]'
        assert observation.substitution.to_dict() == {}
        assert str(observation.proof_sequence) == '[st0: [big_f(_28061), big_f(f(_28061))]]'

    def test_time(self):
        # ARRANGE
        problem = "tests/icnf_problems/SWV230+1.p"
        env = ConnectionEnv(problem, settings=self.settings)
        # ACT
        for i in range(100):
            action = env.action_space[0]
            print(env.state)
            print(action)
            observation, reward, done, info = env.step(action)
            if done:
                break