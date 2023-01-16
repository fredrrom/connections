from cops.utils.primitives import *


def unify(x, y, s={}):
    if s is None:
        return None
    elif x == y:
        return s
    elif isinstance(x, Variable):
        return unify_var(x, y, s)
    elif isinstance(y, Variable):
        return unify_var(y, x, s)
    elif isinstance(x, Expression) and isinstance(y, Expression):
        return unify(x.args, y.args, unify(x.symbol, y.symbol, s))
    elif isinstance(x, tuple) and isinstance(y, tuple) and len(x) == len(y):
        if not x:
            return s
        return unify(x[1:], y[1:], unify(x[0], y[0], s))
    else:
        return None


def unify_var(var, x, s):
    if var in s:
        return unify(s[var], x, s)
    elif x in s:
        return unify(var, s[x], s)
    elif occur_check(var, x, s):
        return None
    else:
        new_s = {**s, var: x}
        cascade_substitution(new_s)
        return new_s


def occur_check(var, x, s):
    if var == x:
        return True
    elif isinstance(x, Variable) and x in s:
        return occur_check(var, s[x], s)
    elif isinstance(x, Expression):
        return any(occur_check(var, arg, s) for arg in x.args)
    else:
        return False


def subst(s, x):
    if isinstance(x, Constant):
        return x
    elif isinstance(x, Variable):
        return s.get(x, x)
    elif isinstance(x, Function):
        return Function(x.symbol, tuple(subst(s, arg) for arg in x.args), prefix=x.prefix, is_pre=x.is_pre)
    else:
        return Literal(
            x.symbol,
            tuple(subst(s, arg) for arg in x.args),
            prefix=x.prefix,
            neg=x.neg,
            matrix_pos=x.matrix_pos,
        )


def cascade_substitution(s):
    for x in s:
        s[x] = subst(s, s.get(x))
        if isinstance(s.get(x), Expression) and not isinstance(s.get(x), Variable):
            # Ensure Function Terms are correct updates by passing over them again
            s[x] = subst(s, s.get(x))


def pre_unify(l, m, r, s={}, counter=0):
    match (l, m, r):
        case ([], [], []):
            return s
    match (l, m, r):
        case ([], [], [X, *u]):
            res = pre_unify([X, *u], [], [], {**s}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([X, *u], [], [Y, *w]) if X == Y:
            res = pre_unify([*u], [], [*w], {**s}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([a, *u], [], [V, *w]) if isinstance(a, Constant) and isinstance(V, Variable):
            res = pre_unify([V, *w], [], [a, *u], {**s}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [*z], []) if isinstance(V, Variable):
            res = pre_unify([*u], [], [], {**s, V: [*z]}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [], [a, *w]) if isinstance(a, Constant) and isinstance(V, Variable):
            res = pre_unify([*u], [], [a, *w], {**s, V: []}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [*z], [a, b, *w]) if isinstance(a, Constant) and isinstance(b, Constant) and isinstance(V,
                                                                                                               Variable):
            res = pre_unify([*u], [], [b, *w], {**s, V: [*z, a]}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, Y, *u], [], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat, Variable):
            res = pre_unify([V_hat, *w], [V], [Y, *u], {**s}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, Y, *u], [X, *z], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat,
                                                                                                         Variable):
            V_dash = Variable('_gen' + str(counter))
            counter = counter + 1
            res = pre_unify([V_hat, *w], [V_dash], [Y, *u], {**s, V: [X, *z, V_dash]}, counter)
            if res is not None: return res
    match (l, m, r):
        case ([V, *u], [*z], [X, *w]) if isinstance(V, Variable) and V != X and (
                    (not u) or w or isinstance(X, Constant)):
            res = pre_unify([V, *u], [*z, X], [*w], {**s}, counter)
            if res is not None: return res
    return None


def pre_unify_all(l, m, r, s={}, unifiers=[], counter=0):
    match (l, m, r):
        case ([], [], []):
            unifiers.append(s)
    match (l, m, r):
        case ([], [], [X, *u]):
            pre_unify_all([X, *u], [], [], {**s}, unifiers, counter)
    match (l, m, r):
        case ([X, *u], [], [Y, *w]) if X == Y:
            pre_unify_all([*u], [], [*w], {**s}, unifiers, counter)
    match (l, m, r):
        case ([a, *u], [], [V, *w]) if isinstance(a, Constant) and isinstance(V, Variable):
            pre_unify_all([V, *w], [], [a, *u], {**s}, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [*z], []) if isinstance(V, Variable):
            pre_unify_all([*u], [], [], {**s, V: [*z]}, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [], [a, *w]) if isinstance(a, Constant) and isinstance(V, Variable):
            pre_unify_all([*u], [], [a, *w], {**s, V: []}, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [*z], [a, b, *w]) if isinstance(a, Constant) and isinstance(b, Constant) and isinstance(V,
                                                                                                               Variable):
            pre_unify_all([*u], [], [b, *w], {**s, V: [*z, a]}, unifiers, counter)
    match (l, m, r):
        case ([V, Y, *u], [], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat, Variable):
            pre_unify_all([V_hat, *w], [V], [Y, *u], {**s}, unifiers, counter)
    match (l, m, r):
        case ([V, Y, *u], [X, *z], [V_hat, *w]) if V != V_hat and isinstance(V, Variable) and isinstance(V_hat,
                                                                                                         Variable):
            V_dash = Variable('_gen' + str(counter))
            counter = counter + 1
            pre_unify_all([V_hat, *w], [V_dash], [Y, *u], {**s, V: [X, *z, V_dash]}, unifiers, counter)
    match (l, m, r):
        case ([V, *u], [*z], [X, *w]) if isinstance(V, Variable) and V != X and (
                    (not u) or w or isinstance(X, Constant)):
            pre_unify_all([V, *u], [*z, X], [*w], {**s}, unifiers, counter)
    return unifiers, counter


def pre_unify_list(equations, s={}, counter=0):
    l1, l2 = equations.pop()
    unifiers, counter = pre_unify_all(l1, [], l2, s=s, unifiers=[], counter=counter)
    if not equations:
        if not unifiers:
            return None
        else:
            return unifiers[0]

    # Recursively try all possible prefix unifiers
    for unifier in unifiers:

        # Apply prefix unifier to all equations
        equations_mod_unifier = []
        for l, r in equations:
            l_mod_unifier, r_mod_unifier = [], []
            for term in l:
                if term in unifier:
                    l_mod_unifier.extend(unifier[term])
                else:
                    l_mod_unifier.append(term)
            for term in r:
                if term in unifier:
                    r_mod_unifier.extend(unifier[term])
                else:
                    r_mod_unifier.append(term)
            equations_mod_unifier.append((l_mod_unifier, r_mod_unifier))

        res = pre_unify_list(equations_mod_unifier, s=unifier, counter=counter)
        if res is not None:
            return res
