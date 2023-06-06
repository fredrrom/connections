# The prefix unification for D is a simple pattern matching, i.e. the standard term unification can be used.
from connections.utils.unification import *
from connections.utils.unification_intu import flatten_list

# sub returned from unify is the sub to pass on to recursive call
def pre_unify(l_pre, m_pre, r_pre, s={}, counter=0):
    l = flatten_list([subst(s,pre) for pre in l_pre])
    r = flatten_list([subst(s,pre) for pre in r_pre])
    if len(l_pre) != len(r_pre):
        return None
    new_s = {**s}
    for arg_1, arg_2 in zip(l,r):
        new_s = unify(arg_1,arg_2,new_s)
        if new_s is None:
            return None
    return new_s


def pre_unify_all(l_pre, m_pre, r_pre, s={}, unifiers=[], counter=0):
    s = pre_unify(l_pre, m_pre, r_pre, s)
    if s is None:
        return [], counter
    return [s], counter


def pre_unify_list(equations, s={}, counter=0):
    l1, l2 = equations[0]
    equations = equations[1:]
    unifiers, counter = pre_unify_all(l1.args, [], l2.args, s=s)
    if not equations:
        if not unifiers:
            return None
        else:
            return unifiers[0]

    # Recursively try all possible prefix unifiers
    res = None
    for unifier in unifiers:
        res = pre_unify_list(equations, s=unifier)
        if res is not None:
            return res
    return res