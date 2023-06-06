from connections.utils.primitives import *


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
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
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
        return Function(x.symbol, [subst(s, arg) for arg in x.args], prefix=x.prefix)
    else:
        return Literal(
            x.symbol,
            [subst(s, arg) for arg in x.args],
            prefix=x.prefix,
            neg=x.neg,
            matrix_pos=x.matrix_pos,
        )


def cascade_substitution(s):
    for x in s:
        s[x] = subst(s, s.get(x))
        if isinstance(s.get(x), Expression) and not isinstance(s.get(x), Variable):
            s[x] = subst(s, s.get(x))