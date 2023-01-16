import pytest

from cops.utils.unification import *


@pytest.fixture
def symbols():
    sym = {'X': Variable('X'), 'Y': Variable('Y'), 'Z': Variable('Z'), 'a': Constant('a'), 'b': Constant('b')}
    sym['fxy'] = Function('f', (sym['X'], sym['Y']))
    sym['fyx'] = Function('f', (sym['Y'], sym['X']))
    sym['fax'] = Function('f', (sym['a'], sym['X']))
    sym['fab'] = Function('f', (sym['a'], sym['b']))
    sym['fx'] = Function('f', args=(sym['X'],))
    sym['fy'] = Function('f', args=(sym['Y'],))
    sym['fyz'] = Function('f', args=(sym['Y'], sym['Z']))
    sym['ffx'] = Function('f', args=(Function('f', args=(sym['X'],)),))
    sym['fa'] = Function('f', args=(sym['a'],))
    sym['gy'] = Function('g', args=(sym['Y'],))
    sym['ga'] = Function('g', args=(sym['a'],))
    sym['gx'] = Function('g', args=(sym['X'],))
    sym['fgx'] = Function('f', args=(sym['gx'],))
    sym['fgxx'] = Function('f', args=(sym['gx'], sym['X']))
    sym['fya'] = Function('f', args=(sym['Y'], sym['a']))
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


@pytest.fixture
def prefixes():
    syms = {'ABC': [Variable('A'), Variable('B'), Variable('C')], 'abc': [Constant('a'), Constant('b'), Constant('c')],
            'ABCD': [Variable('A'), Variable('B'), Variable('C'), Variable('D')],
            'abcd': [Constant('a'), Constant('b'), Constant('c'), Constant('d')],
            'AbCdE': [Variable('A'), Constant('b'), Variable('C'), Constant('d'), Variable('E')],
            'aBcDe': [Constant('a'), Variable('B'), Constant('c'), Variable('D'), Constant('e')],
            'aBCDE': [Constant('a'), Variable('B'), Variable('C'), Variable('D'), Variable('E')],
            'aBFGH': [Constant('a'), Variable('B'), Variable('F'), Variable('G'), Variable('H')]}
    yield syms


@pytest.fixture
def substitutions(prefixes):
    unify = {}
    unify['all_1'], _ = pre_unify_all(prefixes['ABC'], [], prefixes['abc'], unifiers=[])
    unify['all_2'], _ = pre_unify_all(prefixes['ABCD'], [], prefixes['abcd'], unifiers=[])
    unify['all_3'], _ = pre_unify_all(prefixes['AbCdE'], [], prefixes['aBcDe'], unifiers=[])
    unify['all_4'], _ = pre_unify_all(prefixes['aBCDE'], [], prefixes['aBFGH'], unifiers=[])
    unify['first_1'] = pre_unify(prefixes['ABC'], [], prefixes['abc'])
    unify['first_2'] = pre_unify(prefixes['ABCD'], [], prefixes['abcd'])
    unify['first_3'] = pre_unify(prefixes['AbCdE'], [], prefixes['aBcDe'])
    unify['first_4'] = pre_unify(prefixes['aBCDE'], [], prefixes['aBFGH'])
    equations = [(prefixes['ABC'], prefixes['abc']), (prefixes['ABCD'], prefixes['abcd'])]
    unify['list'] = pre_unify_list(equations)
    yield unify


class TestPreUnify:
    def test_unification_print(self, substitutions):
        print(substitutions['all_1'])
        print(substitutions['all_3'])
        print(substitutions['all_4'])

    def test_prefix_unification_all(self, substitutions):
        assert len(substitutions['all_1']) == 10
        assert len(substitutions['all_2']) == 35
        assert len(substitutions['all_3']) == 3
        assert len(substitutions['all_4']) == 6

    def test_prefix_unification_first(self, substitutions):
        assert substitutions['all_1'][0] == substitutions['first_1']
        assert substitutions['all_2'][0] == substitutions['first_2']
        assert substitutions['all_3'][0] == substitutions['first_3']
        assert substitutions['all_4'][0] == substitutions['first_4']

    def test_prefix_unification_list(self, substitutions):
        print(substitutions['list'])
