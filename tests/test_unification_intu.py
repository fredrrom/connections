import pytest

from cops.utils.unification_intu import *

@pytest.fixture
def prefixes():
    syms = {'ABC': Function('string',[Variable('A'), Variable('B'), Variable('C')]), 
            'abc': Function('string',[Function('a'), Function('b'), Function('c')]),
            'ABCD': Function('string',[Variable('A'), Variable('B'), Variable('C'), Variable('D')]),
            'abcd': Function('string',[Function('a'), Function('b'), Function('c'), Function('d')]),
            'AbCdE': Function('string',[Variable('A'), Function('b'), Variable('C'), Function('d'), Variable('E')]),
            'aBcDe': Function('string',[Function('a'), Variable('B'), Function('c'), Variable('D'), Function('e')]),
            'aBCDE': Function('string',[Function('a'), Variable('B'), Variable('C'), Variable('D'), Variable('E')]),
            'aBFGH': Function('string',[Function('a'), Variable('B'), Variable('F'), Variable('G'), Variable('H')])}
    yield syms


@pytest.fixture
def substitutions(prefixes):
    unify = {}
    unify['all_1'], _ = pre_unify_all(prefixes['ABC'].args, [], prefixes['abc'].args, unifiers=[])
    unify['all_2'], _ = pre_unify_all(prefixes['ABCD'].args, [], prefixes['abcd'].args, unifiers=[])
    unify['all_3'], _ = pre_unify_all(prefixes['AbCdE'].args, [], prefixes['aBcDe'].args, unifiers=[])
    unify['all_4'], _ = pre_unify_all(prefixes['aBCDE'].args, [], prefixes['aBFGH'].args, unifiers=[])
    unify['first_1'] = pre_unify(prefixes['ABC'].args, [], prefixes['abc'].args)
    unify['first_2'] = pre_unify(prefixes['ABCD'].args, [], prefixes['abcd'].args)
    unify['first_3'] = pre_unify(prefixes['AbCdE'].args, [], prefixes['aBcDe'].args)
    unify['first_4'] = pre_unify(prefixes['aBCDE'].args, [], prefixes['aBFGH'].args)
    equations = [(prefixes['ABC'], prefixes['abc']), (prefixes['ABCD'], prefixes['abcd'])]
    unify['list'] = pre_unify_list(equations)
    yield unify


class TestPreUnify:
    def test_flatten(self):
        a = Function('string',[Function('string',[Variable('X')]),Variable('Y')])
        b = Function('string',[Function('c_skolem',[Variable('X'),Function('string',[a])]),a])
        c = Function('string',[a,b]) 

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

    def test_prefix_unification_list2(self):
        a_1 = Function('c_skolem',args=[Constant('1'),Constant('a')])
        b_1 = Function('h',args=[Function('f_skolem',args=[Constant('1'),Constant('a')])])
        c_1 = Function('c_skolem',args=[Constant('2'),b_1,Constant('a')])
        pre_1 = Function('string',args=[a_1,c_1])

        a_2 = Function('c_skolem',args=[Constant('1'),Constant('a')])
        b_2 = Variable('V')
        c_2 = Function('c_skolem',args=[Constant('2'),b_2,Constant('a')])
        pre_2 = Function('string',args=[a_2,c_2])

        a_3 = Function('c_skolem',args=[Constant('1'),Constant('a')])
        b_3 = Function('f',args=[Function('f_skolem',args=[Constant('1'),Constant('a')])])
        c_3 = Function('c_skolem',args=[Constant('2'),b_3,Constant('a')])
        pre_3 = Function('string',args=[a_3,c_3])

        print(pre_unify_list([(pre_1,pre_2),(pre_2,pre_3)]))

    def test_prefix_unification_list3(self):
        x = Function('string',args=[Variable('X')])
        zy = Function('string',args=[Variable('Z'),Variable('Y')])
        cw1 = Function('string',args=[Function('c_skolem',args=[Constant('14')]), Variable('W1')])
        z = Function('string',args=[Variable('Z')])
        ab = Function('string',args=[Variable('A'),Variable('B')])
        zc = Function('string',args=[Variable('Z'),Function('c_skolem',args=[Constant('7')])])
        a = Function('string',args=[Variable('A')])
        c = Function('string',args=[Function('c_skolem',args=[Constant('14')])])
        print(pre_unify_list([(zy,cw1),(ab,zc),(a,c)]))

    def test_prefix_unification(self):
        ABCDE = Function('string',args=[Variable('A'),Variable('B'), Variable('C'), Variable('D'), Variable('E')])
        fghcc = Function('string',args=[Variable('F'),Variable('G'), Variable('H'), 
                                        Function('c_skolem',args=[Constant('12'),
                                                                  Variable('H'),
                                                                  Function('f_skolem',args=[Constant('16')]),
                                                                  Variable('G'), 
                                                                  Function('f_skolem',args=[Constant('17')]),
                                                                  Variable('F')]), 
                                        Function('c_skolem',args=[Constant('15'),
                                                                  Variable('H'),
                                                                  Function('f_skolem',args=[Constant('16')]),
                                                                  Variable('G'), 
                                                                  Function('f_skolem',args=[Constant('17')]),
                                                                  Variable('F')])])
        
        print(pre_unify(ABCDE.args, [], fghcc.args))