import pytest

from cops.calculi.classical import *
from cops.utils.primitives import *


class TestClassicalState:
    # ARRANGE
    env = ConnectionEnv('tests/cnf_problems/SYN081+1.cnf')
    state = env.state

    def test_initial_states(self):
        assert isinstance(self.state, ConnectionState)
        assert isinstance(self.state.matrix, Matrix)
        assert isinstance(self.state.goal.literal, Literal)
        assert str([child.literal for child in self.state.tableau.children]) == '[big_f(_28061), big_f(f(_28061))]'
        assert str(self.state.tableau.children[0].literal) == str(self.state.goal.literal)
        assert self.state.tableau.children[0].children == []
        assert self.state.goal.depth == 1
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


class TestConnectionEnv:
    # ARRANGE
    env = ConnectionEnv('tests/cnf_problems/SYN081+1.cnf')

    def test_step(self):
        # ARRANGE
        observation = self.env.reset()
        action = self.env.action_space[0]

        # ACT
        observation, reward, done, info = self.env.step(action)

        # ASSERT
        assert str(action) == 'ex0: big_f(_28061) -> [big_f(_34362), -big_f(f(_34362))]'
        assert observation.max_depth == 2
        assert observation.goal.depth == 1
        assert str(self.env.action_space) == '[ex1: big_f(_28061) -> [-big_f(f(_28063)), -big_f(_28063)],' \
                                             ' ex2: big_f(_28061) -> [-big_f(f(_28064)), -big_f(_28064)]]'
        assert observation.substitution == {}
        assert observation.proof_sequence == []
