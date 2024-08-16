from connections.env import *
from connections.calculi.classical import *
from connections.utils.primitives import *


class TestClassicalState:
    # ARRANGE
    env = ConnectionEnv('tests/cnf_problems/SYN081+1.cnf')
    state = env.state

    def test_initial_states(self):
        assert isinstance(self.state, ConnectionState)
        assert isinstance(self.state.matrix, Matrix)

    def test_start_states(self):
        action = self.env.action_space[0]

        # ACT
        self.state, reward, done, info = self.env.step(action)
        assert isinstance(self.state.goal.literal, Literal)
        assert str([child.literal for child in self.state.tableau.children]) == '[big_f(_131041), big_f(f(_131041))]'
        assert str(self.state.tableau.children[0].literal) == str(self.state.goal.literal)
        assert self.state.tableau.children[0].children == []
        assert self.state.goal.depth == 0
        assert self.state.tableau.literal is None

    def test_extensions(self):
        # ARRANGE
        neg_lits = self.state.matrix.complements(self.state.goal.literal)

        # ASSERT
        assert str(self.state.goal.literal) == 'big_f(_131041)'
        assert neg_lits == [(0, 1), (2, 0), (2, 1)]
        assert str(self.state._extensions()) == '[ex0: big_f(_131041) -> [big_f(_134445), -big_f(f(_134445))],' \
                                                ' ex1: big_f(_131041) -> [-big_f(_131046), -big_f(f(_131046))],' \
                                                ' ex2: big_f(_131041) -> [-big_f(_131047), -big_f(f(_131047))]]'
        assert len(self.state.goal.actions) == 4
        assert self.state.goal.num_attempted == 0

class TestConnectionEnv:
    # ARRANGE
    settings = Settings(iterative_deepening=True)
    env = ConnectionEnv('tests/cnf_problems/SYN081+1.cnf', settings=settings)

    def test_iterative_deepening_steps(self):
        # ARRANGE
        action = self.env.action_space[0]
        print(action)

        # ACT
        observation, reward, done, info = self.env.step(action)
        action = self.env.action_space[0]
        print(observation)
        print(action)

        # ACT
        observation, reward, done, info = self.env.step(action)

        # ASSERT
        assert str(action) == 'ex0: big_f(_131041) -> [big_f(_134442), -big_f(f(_134442))]'
        assert observation.max_depth == 1
        assert observation.goal.depth == 1

        action = self.env.action_space[0]

        # ACT
        observation, reward, done, info = self.env.step(action)
        assert str(self.env.action_space) == '[ex1: big_f(_131041) -> [-big_f(_131043), -big_f(f(_131043))],'\
                                             ' ex2: big_f(_131041) -> [-big_f(_131044), -big_f(f(_131044))],'\
                                             ' Backtrack]'
    
        assert str(observation.substitution) == '{}'
        assert str(observation.proof_sequence) == '[st0: [big_f(_131041), big_f(f(_131041))]]'

    
    def test_time(self):
        # ARRANGE
        settings = Settings(iterative_deepening=True)
        problem = "tests/cnf_problems/SET027+3.p"
        env = ConnectionEnv(problem, settings=settings)
        # ACT
        for i in range(83):
            action = env.action_space[0]
            # print("-------------------------")
            # print(env.state.tableau)
            # print(env.state.substitution.to_dict())
            # print(env.state.goal)
            # print(action)
            # print(env.state.substitution.parent)
            # print("-------------------------")
            observation, reward, done, info = env.step(action)
            if done:
                break