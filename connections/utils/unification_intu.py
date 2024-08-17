from connections.utils.unification import *
from copy import deepcopy

# sub returned from unify is the sub to pass on to recursive call
def pre_unify(l_pre, m_pre, r_pre, s=Substitution(), counter=0):
    l = flatten_list([s(pre) for pre in l_pre])
    m = flatten_list([s(pre) for pre in m_pre])
    r = flatten_list([s(pre) for pre in r_pre])
    counter = counter + 1
    match (l, m, r):
        case ([], [], []):
            return s
    match (l, m, r):
        case ([], [], [X, *u]):
            res = pre_unify([X, *u], [], [], deepcopy(s), counter)
            if res is not None: return res
    match (l, m, r):
        case ([X, *u], [], [Y, *w]) if (isinstance(X, Variable) and isinstance(Y, Variable) and X == Y): 
            res = pre_unify([*u], [], [*w], deepcopy(s), counter)
            if res is not None: return res
        case ([X, *u], [], [Y, *w]) if (isinstance(X, Function) and isinstance(Y, Function)):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(X,Y)
            if unifies:
                res = pre_unify([*u], [], [*w], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([a, *u], [], [V, *w]) if isinstance(a, Function) and isinstance(V, Variable):
            res = pre_unify([V, *w], [], [a, *u], deepcopy(s), counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [*z], []) if isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=z))
            if unifies:
                res = pre_unify([*u], [], [], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([V, *u], [], [a, *w]) if isinstance(a, Function) and isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[]))
            if unifies:
                res = pre_unify([*u], [], [a, *w], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([V, *u], [*z], [a, b, *w]) if isinstance(a, Function) and isinstance(b, Function) and isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[*z, a]))
            if unifies:
                res = pre_unify([*u], [], [b, *w], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([V, Y, *u], [], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat, Variable):
            res = pre_unify([V_hat, *w], [V], [Y, *u], deepcopy(s), counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, Y, *u], [X, *z], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat, Variable):
            V_dash = Variable('_gen' + str(counter))
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[X, *z, V_dash]))
            if unifies:
                res = pre_unify([V_hat, *w], [V_dash], [Y, *u], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([V, *u], [*z], [X, *w]) if isinstance(V, Variable) and V != X and (
                    (not u) or w or isinstance(X, Function)):
            res = pre_unify([V, *u], [*z, X], [*w], deepcopy(s), counter)
            if res is not None: return res
    return None

def pre_unify_all(l_pre, m_pre, r_pre, s=Substitution(), unifiers=[], counter=0):
    l = flatten_list([s(pre) for pre in l_pre])
    m = flatten_list([s(pre) for pre in m_pre])
    r = flatten_list([s(pre) for pre in r_pre])
    counter = counter + 1
    match (l, m, r):
        case ([], [], []):
            unifiers.append(s)
    match (l, m, r):
        case ([], [], [X, *u]):
            pre_unify_all([X, *u], [], [], deepcopy(s), unifiers, counter)
    match (l, m, r):
        case ([X, *u], [], [Y, *w]) if (isinstance(X, Variable) and isinstance(Y, Variable) and X == Y): 
            pre_unify_all([*u], [], [*w], deepcopy(s), unifiers, counter)
        case ([X, *u], [], [Y, *w]) if (isinstance(X, Function) and isinstance(Y, Function)):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(X,Y)
            if unifies:
                pre_unify_all([*u], [], [*w], new_s, unifiers, counter)
    match (l, m, r):
        case ([a, *u], [], [V, *w]) if isinstance(a, Function) and isinstance(V, Variable):
            pre_unify_all([V, *w], [], [a, *u], deepcopy(s), unifiers, counter)
    match (l, m, r):
        case ([V, *u], [*z], []) if isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=z))
            if unifies:
                pre_unify_all([*u], [], [], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [], [a, *w]) if isinstance(a, Function) and isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[]))
            if unifies:
                pre_unify_all([*u], [], [a, *w], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [*z], [a, b, *w]) if isinstance(a, Function) and isinstance(b, Function) and isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[*z, a]))
            if unifies:
                pre_unify_all([*u], [], [b, *w], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, Y, *u], [], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat, Variable):
            pre_unify_all([V_hat, *w], [V], [Y, *u], deepcopy(s), unifiers, counter)
    match (l, m, r):
        case ([V, Y, *u], [X, *z], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat, Variable):
            V_dash = Variable('_gen' + str(counter))
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[X, *z, V_dash]))
            if unifies:
                pre_unify_all([V_hat, *w], [V_dash], [Y, *u], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [*z], [X, *w]) if isinstance(V, Variable) and V != X and (
                    (not u) or w or isinstance(X, Function)):
            pre_unify_all([V, *u], [*z, X], [*w], deepcopy(s), unifiers, counter)
    return unifiers, counter

def flatten_list(args):
    flatten_list = []
    for arg in args:
        if arg.symbol == 'string':
            flatten_list.extend(flatten(arg).args)
        else:
            flatten_list.append(flatten(arg))
    return flatten_list

def flatten(string):
    flattened_args = []
    for term in string.args:
        if term.symbol == 'string':
            for subterm in flatten(term).args:
                flattened_args.append(subterm)
        else:
            flattened_args.append(flatten(term))
    string.args = flattened_args
    return string

def pre_unify_list(equations, s=Substitution(), counter=0):
    l1, l2 = equations[0]
    equations = equations[1:]
    unifiers, counter = pre_unify_all(l1.args, [], l2.args, s=s, unifiers=[], counter=counter)
    if not equations:
        if not unifiers:
            return None
        else:
            return unifiers[0]

    # Recursively try all possible prefix unifiers
    res = None
    for unifier in unifiers:
        res = pre_unify_list(equations, s=unifier, counter=counter)
        if res is not None:
            return res
    return res
