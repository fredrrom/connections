from cops.calculi.intuitionistic import *
from cops.utils.primitives import *


class TestClassicalState:
    # ARRANGE
    env = IConnectionEnv('tests/icnf_problems/SYN081+1.cnf')
    state = env.reset()

    def test_initial_states(self):
        assert isinstance(self.state, IConnectionState)
        assert isinstance(self.state.matrix, Matrix)
        assert isinstance(self.state.goal.literal, Literal)
        assert str([child.literal for child in self.state.tableau.children]) == '[big_f(_34251), big_f(f(_34251))]'
        assert str(self.state.tableau.children[0].literal) == str(self.state.goal.literal)
        assert self.state.tableau.children[0].children == []
        assert self.state.goal.depth == 1
        assert self.state.tableau.literal is None

    def test_extensions(self):
        # ARRANGE
        neg_lits = self.state.matrix.complements(self.state.goal.literal)

        # ASSERT
        assert str(self.state.goal.literal) == 'big_f(_34251)'
        assert neg_lits == [(0, 1), (2, 0), (2, 1)]
        assert str(self.state._extensions()) == '[ex0: big_f(_34251) -> [big_f(_35885), -big_f(f(_35885))],' \
                                                ' ex1: big_f(_34251) -> [-big_f(_34256), -big_f(f(_34256))],' \
                                                ' ex2: big_f(_34251) -> [-big_f(_34257), -big_f(f(_34257))]]'


class TestConnectionEnv:
    # ARRANGE
    env = IConnectionEnv('tests/icnf_problems/SYN081+1.cnf')

    def test_step(self):
        # ARRANGE
        observation = self.env.reset()
        action = self.env.action_space[0]

        # ACT
        observation, reward, done, info = self.env.step(action)

        # ASSERT
        assert str(action) == 'ex0: big_f(_34251) -> [big_f(_35882), -big_f(f(_35882))]'
        assert observation.max_depth == 2
        assert observation.goal.depth == 1
        assert str(self.env.action_space) == '[ex1: big_f(_34251) -> [-big_f(_34253), -big_f(f(_34253))],' \
                                             ' ex2: big_f(_34251) -> [-big_f(_34254), -big_f(f(_34254))]]'
        assert observation.substitution == {}
        assert observation.proof_sequence == []