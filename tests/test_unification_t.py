import pytest

from connections.utils.unification_t import *

@pytest.fixture
def prefixes():
    syms = {'ABC': Function('string',[Variable('A'), Variable('B'), Variable('C')]), 
            'abc': Function('string',[Function('a'), Function('b'), Function('c')]),
            'ab': Function('string',[Function('a'), Function('b')]),
            'ABCD': Function('string',[Variable('A'), Variable('B'), Variable('C'), Variable('D')]),
            'EFG': Function('string',[Variable('E'), Variable('F'), Variable('G')]),
            'EFGH': Function('string',[Variable('E'), Variable('F'), Variable('G'), Variable('H')]),
            'AbCd': Function('string',[Variable('A'), Function('b'), Variable('C'), Function('d')]),
            'eFgH': Function('string',[Function('e'), Variable('F'), Function('g'), Variable('H')]),
            'left': Function('string',[Function('c_skolem',[Function('1'),Function('c_skolem',[Function('2')])])]),
            'right': Function('string',[Function('c_skolem',[Function('1'),Variable('_76862')])])
            }
    yield syms

@pytest.fixture
def substitutions(prefixes):
    unify = {}
    unify['first_1'] = pre_unify(prefixes['ABC'].args, [], prefixes['EFG'].args)
    unify['first_2'] = pre_unify(prefixes['ABCD'].args, [], prefixes['EFGH'].args)
    unify['first_3'] = pre_unify(prefixes['left'].args, [], prefixes['right'].args)
    unify['all_1'], _ = pre_unify_all(prefixes['ABCD'].args, [], prefixes['ab'].args, unifiers=[])
    unify['all_2'], _ = pre_unify_all(prefixes['ABCD'].args, [], prefixes['abc'].args, unifiers=[])
    unify['all_3'], _ = pre_unify_all(prefixes['AbCd'].args, [], prefixes['eFgH'].args, unifiers=[])
    unify['all_first_1'], _ = pre_unify_all(prefixes['ABC'].args, [], prefixes['EFG'].args, unifiers=[])
    unify['all_first_2'], _ = pre_unify_all(prefixes['ABCD'].args, [], prefixes['EFGH'].args, unifiers=[])
    yield unify

class TestPreUnify:
    def test_flatten(self):
        a = Function('string',[Function('string',[Variable('X')]),Variable('Y')])
        b = Function('string',[Function('c_skolem',[Variable('X'),Function('string',[a])]),a])
        c = Function('string',[a,b]) 

    def test_unification_print(self, substitutions):
        print(substitutions['first_1'])
        print(substitutions['first_2'])
        print(substitutions['first_3'])
        print(substitutions['all_1'])
        print(substitutions['all_2'])
        print(substitutions['all_3'])

    def test_prefix_unification_all(self, substitutions):
        assert len(substitutions['all_1']) == 6
        assert len(substitutions['all_2']) == 4
        assert len(substitutions['all_3']) == 1
        print(len(substitutions['all_first_1']))
        print(len(substitutions['all_first_2']))