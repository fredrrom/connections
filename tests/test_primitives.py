from cops.utils.primitives import *


class TestVariable:
    # ARRANGE
    x = Variable("X")

    def test_variable_copy(self):
        # ACT
        y = self.x.copy(1)

        # ASSERT
        assert str(self.x) + '1' == str(y)


class TestFunction:
    # ARRANGE
    x = Variable("X")
    f = Function("f", (x,))

    def test_function_str(self):
        # ACT and ASSERT
        assert str(self.f) == 'f(X)'


class TestLiteral:
    # ARRANGE
    x = Variable("X")
    f = Function("f", (x,))
    p = Literal("p", (f,))

    def test_literal_str(self):
        # ACT and ASSERT
        assert str(self.p) == 'p(f(X))'

    def test_literal_copy(self):
        # ACT
        y = self.p.copy(1)

        # ASSERT
        assert 'p(f(X1))' == str(y)


class TestMatrix:
    x = Variable("X")
    f = Function("f", (x,))
    p = Literal("p", (f,))
    q = Literal("p", (f,), neg=True)
    m = Matrix([[p], [q]])

    def test_complements(self):
        # ACT
        comp = self.m.complements(self.p)

        # ASSERT
        assert comp == [(1, 0)]

    def test_copy(self):
        # ACT
        copy = self.m.copy(0)

        # ASSERT
        assert str(copy) == '[p(f(X1))]'

    def test_lit_idx(self):
        # ACT
        idx = self.m.lit_idx(self.p)

        # ASSERT
        assert idx == 0

# todo add test problem directory
# todo add parsing test