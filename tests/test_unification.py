import pytest

from cops.utils.unification import *


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
    def test_unify_constants_and_variables(self, symbols):
        assert unify(symbols['a'], symbols['a']) == {}
        assert unify(symbols['a'], symbols['b']) is None
        assert unify(symbols['X'], symbols['X']) == {}
        assert unify(symbols['a'], symbols['X']) == {symbols['X']: symbols['a']}
        assert unify(symbols['X'], symbols['Y']) == {symbols['X']: symbols['Y']}

    def test_unify_functions(self, symbols):
        assert unify(symbols['fax'], symbols['fab']) == {symbols['X']: symbols['b']}
        assert unify(symbols['fa'], symbols['ga']) is None
        assert unify(symbols['fx'], symbols['fy']) == {symbols['X']: symbols['Y']}
        assert unify(symbols['fx'], symbols['gy']) is None
        assert unify(symbols['fx'], symbols['fyz']) is None
        assert unify(symbols['fgx'], symbols['fy']) == {symbols['Y']: symbols['gx']}
        assert unify(symbols['fgxx'], symbols['fya']) == {symbols['X']: symbols['a'], symbols['Y']: symbols['ga']}
        assert unify(symbols['fxy'], symbols['fyx']) == {symbols['X']: symbols['Y']}
        assert unify(symbols['fxy'], symbols['fab']) == {symbols['X']: symbols['a'], symbols['Y']: symbols['b']}

    def test_unify_occur_check(self, symbols):
        assert unify(symbols['fx'], symbols['ffx']) is None

    def test_unify_nested(self, symbols):
        sub1 = unify(symbols['X'], symbols['Y'])
        sub2 = unify(symbols['a'], symbols['Y'])
        sub3 = unify(symbols['X'], symbols['a'])
        assert unify(symbols['Y'], symbols['a'], sub1) == {symbols['X']: symbols['a'], symbols['Y']: symbols['a']}
        assert unify(symbols['X'], symbols['Y'], sub2) == {symbols['X']: symbols['a'], symbols['Y']: symbols['a']}
        assert unify(symbols['b'], symbols['X'], sub3) is None


