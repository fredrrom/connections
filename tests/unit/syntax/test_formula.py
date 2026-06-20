from connections.syntax.formula import Atom, Function, Variable


def test_variable_vid_is_preserved():
    x = Variable("X", vid=1)
    assert x.vid == 1


def test_function_symbol_and_args():
    x = Variable("X")
    f = Function("f", (x,))
    assert f.symbol == "f"
    assert f.args == (x,)


def test_atom_symbol_and_args():
    x = Variable("X")
    f = Function("f", (x,))
    atom = Atom("p", (f,))
    assert atom.symbol == "p"
    assert atom.args == (f,)
