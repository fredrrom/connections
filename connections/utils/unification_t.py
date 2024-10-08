# The prefix unification for T is specified by a set of rewriting rules like intuitionistic prefix unification.
from copy import deepcopy

from connections.utils.unification import *
from connections.utils.unification_intu import flatten_list

def pre_unify(l_pre, m_pre, r_pre, s=Substitution(), counter=0):
    l = flatten_list([s(pre) for pre in l_pre])
    m = flatten_list([s(pre) for pre in m_pre])
    r = flatten_list([s(pre) for pre in r_pre])
    
    match (l, m, r):
        case ([], [], []):
            return s
    match (l, m, r):
        case ([], [], [X, *u]):
            res = pre_unify([X, *u], [], [], deepcopy(s), counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [], []) if isinstance(V, Variable): 
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[]))
            if unifies:
                res = pre_unify([*u], [], [], new_s, counter)
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
        case ([V, *u], [], [X, *w]) if isinstance(V, Variable) and V != X:
            res = pre_unify([V,*u], [X], [*w], deepcopy(s), counter)
            if res is not None: return res
    match (l, m, r):
        case ([a, *u], [], [V, *w]) if isinstance(a, Function) and isinstance(V, Variable):
            res = pre_unify([V,*w], [a], [*u], deepcopy(s), counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [], [U, *w]) if isinstance(V, Variable) and isinstance(U, Variable) and X != V:
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(U,Function('string',args=[]))
            if unifies:
                res = pre_unify([*w], [V], [*u], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([V, *u], [X], [*w]) if isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[]))
            if unifies:
                res = pre_unify([*u], [X], [*w], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([V, *u], [X], [*w]) if isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,X)
            if unifies:
                res = pre_unify([*u], [], [*w], new_s, counter)
                if res is not None: return res
    match (l, m, r):
        case ([a, *u], [V], [*w]) if isinstance(a,Function) and isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,a)
            if unifies:
                res = pre_unify([*u], [], [*w], new_s, counter)
                if res is not None: return res
    return None

def pre_unify_all(l_pre, m_pre, r_pre, s=Substitution(), unifiers=[], counter=0):
    l = flatten_list([s(pre) for pre in l_pre])
    m = flatten_list([s(pre) for pre in m_pre])
    r = flatten_list([s(pre) for pre in r_pre])

    match (l, m, r):
        case ([], [], []):
            unifiers.append(s)
    match (l, m, r):
        case ([], [], [X, *u]):
            pre_unify_all([X, *u], [], [], deepcopy(s), unifiers, counter)
    match (l, m, r):
        case ([V, *u], [], []) if isinstance(V, Variable): 
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[]))
            if unifies:
                pre_unify_all([*u], [], [], new_s, unifiers, counter)
    match (l, m, r):
        case ([X, *u], [], [Y, *w]) if (isinstance(X, Variable) and isinstance(Y, Variable) and X == Y): 
            pre_unify_all([*u], [], [*w], deepcopy(s), unifiers, counter)
        case ([X, *u], [], [Y, *w]) if (isinstance(X, Function) and isinstance(Y, Function)):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(X,Y)
            if unifies:
                pre_unify_all([*u], [], [*w], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [], [X, *w]) if isinstance(V, Variable) and V != X:
            pre_unify_all([V,*u], [X], [*w], deepcopy(s), unifiers, counter)
    match (l, m, r):
        case ([a, *u], [], [V, *w]) if isinstance(a, Function) and isinstance(V, Variable):
            pre_unify_all([V,*w], [a], [*u], deepcopy(s), unifiers, counter)
    match (l, m, r):
        case ([V, *u], [], [U, *w]) if isinstance(V, Variable) and isinstance(U, Variable) and X != V:
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(U,Function('string',args=[]))
            if unifies:
                pre_unify_all([*w], [V], [*u], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [X], [*w]) if isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,Function('string',args=[]))
            if unifies:
                pre_unify_all([*u], [X], [*w], new_s, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [X], [*w]) if isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,X)
            if unifies:
                pre_unify_all([*u], [], [*w], new_s, unifiers, counter)
    match (l, m, r):
        case ([a, *u], [V], [*w]) if isinstance(a,Function) and isinstance(V, Variable):
            new_s = deepcopy(s)
            unifies, _ = new_s.unify(V,a)
            if unifies:
                pre_unify_all([*u], [], [*w], new_s, unifiers, counter)
    return unifiers, counter

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
