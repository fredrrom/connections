import pytest

from connections.utils.unification import *
from connections.utils.primitives import *

@pytest.fixture
def symbols():
    sym = {'X': Variable('X'), 'Y': Variable('Y'), 'Z': Variable('Z'), 'a': Constant('a'), 'b': Constant('b')}
    sym['fxy'] = Function('f', [sym['X'], sym['Y']])
    sym['fyx'] = Function('f', [sym['Y'], sym['X']])
    sym['fax'] = Function('f', [sym['a'], sym['X']])
    sym['fab'] = Function('f', [sym['a'], sym['b']])
    sym['fx'] = Function('f', args=[sym['X']])
    sym['fy'] = Function('f', args=[sym['Y']])
    sym['fyz'] = Function('f', args=[sym['Y'], sym['Z']])
    sym['ffx'] = Function('f', args=[Function('f', args=[sym['X']])])
    sym['fa'] = Function('f', args=[sym['a']])
    sym['gy'] = Function('g', args=[sym['Y']])
    sym['ga'] = Function('g', args=[sym['a']])
    sym['gx'] = Function('g', args=[sym['X']])
    sym['fgx'] = Function('f', args=[sym['gx']])
    sym['fgxx'] = Function('f', args=[sym['gx'], sym['X']])
    sym['fya'] = Function('f', args=[sym['Y'], sym['a']])
    yield sym


class TestUnify:
    sub = Substitution()

    def test_unify_constants_and_variables(self, symbols):
        assert self.sub.can_unify(symbols['a'], symbols['a']) == (True, [])
        assert self.sub.can_unify(symbols['a'], symbols['b']) == (False, [])
        assert self.sub.can_unify(symbols['X'], symbols['X']) == (True, [symbols['X']])
        assert self.sub.can_unify(symbols['a'], symbols['X']) == (True, [symbols['X'], (symbols['X'], symbols['X'], symbols['a'])])
        assert self.sub.can_unify(symbols['X'], symbols['Y']) == (True, [symbols['X'], symbols['Y'], (symbols['X'], symbols['X'], symbols['Y'])])

    def test_unify_functions(self, symbols):
        assert self.sub.can_unify(symbols['fax'], symbols['fab']) == (True, [symbols['X'], (symbols['X'], symbols['X'], symbols['b'])])
        assert self.sub.can_unify(symbols['fa'], symbols['ga']) == (False, [])
        assert self.sub.can_unify(symbols['fx'], symbols['fy']) == (True, [symbols['X'], symbols['Y'], (symbols['X'], symbols['X'], symbols['Y'])])
        assert self.sub.can_unify(symbols['fx'], symbols['gy']) == (False, [])
        assert self.sub.can_unify(symbols['fx'], symbols['fyz']) == (False, [])
        assert self.sub.can_unify(symbols['fgx'], symbols['fy']) == (True, [symbols['Y'], (symbols['Y'], symbols['Y'], symbols['gx'])])
        assert self.sub.can_unify(symbols['fgxx'], symbols['fya']) == (True, [symbols['X'], (symbols['X'], symbols['X'], symbols['a']),
                                                                            symbols['Y'], (symbols['Y'], symbols['Y'], symbols['gx'])])
        assert self.sub.can_unify(symbols['fxy'], symbols['fyx']) == (True, [symbols['Y'], symbols['X'], (symbols['Y'], symbols['Y'], symbols['X'])])
        assert self.sub.can_unify(symbols['fxy'], symbols['fab']) == (True, [symbols['Y'], (symbols['Y'], symbols['Y'], symbols['b']),
                                                                             symbols['X'], (symbols['X'], symbols['X'], symbols['a'])])

    def test_unify_occur_check(self, symbols):
        assert self.sub.can_unify(symbols['fx'], symbols['ffx']) == (False, [symbols['X']])

    def test_unify_incremental(self, symbols):
        sub1 = Substitution()
        sub1.unify(symbols['X'], symbols['Y'])
        sub1.unify(symbols['X'], symbols['a'])
        assert sub1.to_dict() == {symbols['X']: symbols['a'], symbols['Y']: symbols['a']}

        sub2 = Substitution()
        sub2.unify(symbols['a'], symbols['Y'])
        sub2.unify(symbols['X'], symbols['Y'])
        assert sub2.to_dict() == {symbols['X']: symbols['a'], symbols['Y']: symbols['a']}

        sub3 = Substitution()
        sub3.unify(symbols['X'], symbols['a'])
        assert sub3.unify(symbols['b'], symbols['X']) == (False, [])


