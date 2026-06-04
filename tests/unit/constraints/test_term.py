import pytest

from connections.core.formula import Atom, Function, Variable
from connections.core.matrix import Literal
from connections.constraints.term import TermBinding, TermSubstitution, TableauVariable


def binding(variable, target, instance_id=None):
    return variable, (target, instance_id)


@pytest.fixture
def symbols():
    sym = {
        "X": Variable("X"),
        "Y": Variable("Y"),
        "Z": Variable("Z"),
        "Old": Variable("Old", vid=1),
        "New": Variable("New", vid=2),
        "a": Function("a"),
        "b": Function("b"),
    }
    sym["fxy"] = Function("f", (sym["X"], sym["Y"]))
    sym["fyx"] = Function("f", (sym["Y"], sym["X"]))
    sym["fax"] = Function("f", (sym["a"], sym["X"]))
    sym["fab"] = Function("f", (sym["a"], sym["b"]))
    sym["fx"] = Function("f", args=(sym["X"],))
    sym["fy"] = Function("f", args=(sym["Y"],))
    sym["fyz"] = Function("f", args=(sym["Y"], sym["Z"]))
    sym["ffx"] = Function("f", args=(Function("f", args=(sym["X"],)),))
    sym["fa"] = Function("f", args=(sym["a"],))
    sym["ga"] = Function("g", args=(sym["a"],))
    yield sym


class TestTermSubstitution:
    def test_unify_constants_and_variables(self, symbols):
        sub = TermSubstitution()

        assert sub.unify(older=symbols["a"], newer=symbols["a"]) == (True, ())
        assert sub.unify(older=symbols["a"], newer=symbols["b"]) == (False, ())
        assert sub.unify(older=symbols["X"], newer=symbols["X"]) == (True, ())
        assert sub.unify(older=symbols["a"], newer=symbols["X"]) == (
            True,
            (binding(symbols["X"], symbols["a"]),),
        )
        assert sub.unify(older=symbols["Old"], newer=symbols["New"]) == (
            True,
            (binding(symbols["New"], symbols["Old"]),),
        )

    def test_unify_functions(self, symbols):
        sub = TermSubstitution()

        assert sub.unify(older=symbols["fax"], newer=symbols["fab"]) == (
            True,
            (binding(symbols["X"], symbols["b"]),),
        )
        assert sub.unify(older=symbols["fa"], newer=symbols["ga"]) == (False, ())
        assert sub.unify(older=symbols["fx"], newer=symbols["fy"]) == (
            True,
            (binding(symbols["Y"], symbols["X"]),),
        )
        assert sub.unify(older=symbols["fx"], newer=symbols["fyz"]) == (False, ())

    def test_unify_occurs_check(self, symbols):
        sub = TermSubstitution()

        assert sub.unify(older=symbols["fx"], newer=symbols["ffx"]) == (False, ())

    def test_unifiable_from_empty_renames_sides_apart(self, symbols):
        left = Literal(atom=Atom("p", (symbols["X"],)), polarity=True)
        right = Literal(
            atom=Atom("p", (Function("f", (symbols["X"],)),)),
            polarity=False,
        )

        assert TermSubstitution.unifiable_from_empty(older=left, newer=right) is True

    def test_unifiable_from_empty_preserves_repeated_variables(self, symbols):
        left = Literal(
            atom=Atom("p", (symbols["X"], symbols["X"])),
            polarity=True,
        )
        right = Literal(
            atom=Atom("p", (symbols["a"], symbols["b"])),
            polarity=False,
        )

        assert TermSubstitution.unifiable_from_empty(older=left, newer=right) is False

    def test_unifiable_from_empty_ignores_committed_bindings(self, symbols):
        sub = TermSubstitution()
        sub.bind((binding(symbols["X"], symbols["a"]),))
        left = Literal(atom=Atom("p", (symbols["X"],)), polarity=True)
        right = Literal(atom=Atom("p", (symbols["b"],)), polarity=False)

        assert TermSubstitution.unifiable_from_empty(older=left, newer=right) is True
        assert sub.unify(older=left, newer=right) == (False, ())

    def test_unify_does_not_mutate_bindings(self, symbols):
        sub = TermSubstitution()
        before = dict(sub.bindings)

        ok, _ = sub.unify(older=symbols["fax"], newer=symbols["fab"])

        assert ok is True
        assert sub.bindings == before

    def test_unify_literals(self, symbols):
        sub = TermSubstitution()
        left = Literal(atom=Atom("p", (symbols["X"],)), polarity=True)
        right = Literal(atom=Atom("p", (symbols["a"],)), polarity=False)

        ok, bindings = sub.unify(older=left, newer=right)

        assert ok is True
        assert bindings == (binding(symbols["X"], symbols["a"]),)

    def test_unify_incremental_requires_explicit_bind(self, symbols):
        sub1 = TermSubstitution()
        ok, bindings = sub1.unify(older=symbols["X"], newer=symbols["Y"])
        assert ok is True
        sub1.bind(bindings)
        ok, bindings = sub1.unify(older=symbols["X"], newer=symbols["a"])
        assert ok is True
        sub1.bind(bindings)
        assert sub1.to_dict() == {
            symbols["X"]: symbols["a"],
            symbols["Y"]: symbols["a"],
        }

        sub2 = TermSubstitution()
        ok, bindings = sub2.unify(older=symbols["a"], newer=symbols["Y"])
        assert ok is True
        sub2.bind(bindings)
        ok, bindings = sub2.unify(older=symbols["X"], newer=symbols["Y"])
        assert ok is True
        sub2.bind(bindings)
        assert sub2.to_dict() == {
            symbols["X"]: symbols["a"],
            symbols["Y"]: symbols["a"],
        }

        sub3 = TermSubstitution()
        ok, bindings = sub3.unify(older=symbols["X"], newer=symbols["a"])
        assert ok is True
        sub3.bind(bindings)
        assert sub3.unify(older=symbols["b"], newer=symbols["X"]) == (False, ())

    def test_bind_then_unbind_restores_bindings(self, symbols):
        sub = TermSubstitution()
        ok, bindings = sub.unify(older=symbols["X"], newer=symbols["a"])
        assert ok is True

        before = dict(sub.bindings)
        sub.bind(bindings)
        assert sub.to_dict() == {symbols["X"]: symbols["a"]}
        sub.unbind(bindings)
        assert sub.bindings == before

    def test_unbind_owned_by_removes_rule_application_bindings(self, symbols):
        sub = TermSubstitution()
        sub.bind((binding(symbols["X"], symbols["a"]),), owner_app_id=1)
        sub.bind((binding(symbols["Y"], symbols["b"]),), owner_app_id=2)

        sub.unbind_owned_by((1,))

        assert sub.bindings == {symbols["Y"]: (symbols["b"], None)}

    def test_bind_and_unbind_advance_resolve_revision(self, symbols):
        sub = TermSubstitution()
        assert sub.revision == 0

        sub.bind((binding(symbols["X"], symbols["a"]),))
        assert sub.revision == 1
        assert sub._resolve(symbols["X"]) == symbols["a"]
        assert sub._resolve_cache[symbols["X"]].revision == 1

        sub.unbind((binding(symbols["X"], symbols["a"]),))
        assert sub.revision == 2
        assert sub._resolve(symbols["X"]) == symbols["X"]
        assert sub._resolve_cache[symbols["X"]].revision == 2

    def test_unbind_rejects_missing_binding(self, symbols):
        sub = TermSubstitution()

        with pytest.raises(ValueError, match="not present"):
            sub.unbind((binding(symbols["X"], symbols["a"]),))

    def test_unbind_rejects_mismatched_binding_target(self, symbols):
        sub = TermSubstitution()
        sub.bind((binding(symbols["X"], symbols["a"]),))

        with pytest.raises(ValueError, match="different target"):
            sub.unbind((binding(symbols["X"], symbols["b"]),))

    def test_bind_rejects_rebinding(self, symbols):
        sub = TermSubstitution()
        bindings: tuple[TermBinding, ...] = (binding(symbols["X"], symbols["a"]),)

        sub.bind(bindings)

        with pytest.raises(ValueError, match="already bound"):
            sub.bind(bindings)

    def test_bind_rejects_duplicate_variable_in_batch(self, symbols):
        sub = TermSubstitution()
        bindings: tuple[TermBinding, ...] = (
            binding(symbols["X"], symbols["a"]),
            binding(symbols["X"], symbols["b"]),
        )

        with pytest.raises(ValueError, match="same variable twice"):
            sub.bind(bindings)

    def test_unify_keeps_new_variable_bound_to_older_variable_occurrence(self, symbols):
        sub = TermSubstitution()
        older = Variable("Older", vid=3)
        middle = Variable("Middle", vid=2)
        oldest = Variable("Oldest", vid=1)
        newer = Variable("Newer", vid=4)

        sub.bind(
            (
                binding(older, middle),
                binding(middle, oldest),
                binding(oldest, symbols["a"]),
            )
        )

        ok, bindings = sub.unify(older=older, newer=newer)

        assert ok is True
        assert bindings == (binding(newer, older),)

    def test_unify_repeated_new_variable_against_equal_older_variables(self):
        sub = TermSubstitution()
        root = Variable("Root", vid=1)
        left = Variable("Left", vid=2)
        right = Variable("Right", vid=3)
        new = Variable("New", vid=4)
        sub.bind((binding(left, root), binding(right, root)))
        older = Literal(atom=Atom("equal", (left, right)), polarity=True)
        newer = Literal(atom=Atom("equal", (new, new)), polarity=False)

        ok, bindings = sub.unify(older=older, newer=newer)

        assert ok is True
        assert bindings == (binding(new, right),)

    def test_resolution_does_not_compress_tableau_binding_forest(self, symbols):
        sub = TermSubstitution()
        child = Variable("Child", vid=3)
        parent = Variable("Parent", vid=2)
        grandparent = Variable("Grandparent", vid=1)
        sub.bind(
            (
                binding(child, parent),
                binding(parent, grandparent),
                binding(grandparent, symbols["a"]),
            )
        )

        assert sub.to_dict()[child] == symbols["a"]
        assert sub.bindings[child] == (parent, None)
        assert sub.bindings[parent] == (grandparent, None)

    def test_unify_binds_oldest_variable_in_chain_to_new_function(self, symbols):
        sub = TermSubstitution()
        B = Variable("B", vid=2)
        C = Variable("C", vid=1)
        older = Variable("Older", vid=3)
        newer = Variable("Newer", vid=4)

        sub.bind((binding(older, B), binding(B, C)))

        ok, bindings = sub.unify(older=older, newer=Function("f", (newer,)))

        assert ok is True
        assert bindings == (binding(C, Function("f", (newer,))),)

    def test_equal_checks_literals_under_substitution(self, symbols):
        sub = TermSubstitution()
        ok, bindings = sub.unify(older=symbols["X"], newer=symbols["a"])
        assert ok is True
        sub.bind(bindings)

        left_literal = Literal(
            atom=Atom("p", (Function("f", (symbols["X"],)),)),
            polarity=True,
        )
        right_literal = Literal(
            atom=Atom("p", (Function("f", (symbols["a"],)),)),
            polarity=True,
        )

        assert sub.equal(left_literal, right_literal) is True

    def test_complementary_checks_literals_under_substitution(self, symbols):
        sub = TermSubstitution()
        ok, bindings = sub.unify(older=symbols["X"], newer=symbols["a"])
        assert ok is True
        sub.bind(bindings)

        left_literal = Literal(
            atom=Atom("p", (Function("f", (symbols["X"],)),)),
            polarity=True,
        )
        right_literal = Literal(
            atom=Atom("p", (Function("f", (symbols["a"],)),)),
            polarity=False,
        )

        assert sub.complementary(left_literal, right_literal) is True
        assert sub.equal(left_literal, right_literal) is False

    def test_call_applies_substitution_to_literals(self, symbols):
        sub = TermSubstitution()
        ok, bindings = sub.unify(older=symbols["X"], newer=symbols["a"])
        assert ok is True
        sub.bind(bindings)

        literal = Literal(
            atom=Atom("p", (Function("f", (symbols["X"],)),)),
            polarity=True,
        )

        assert sub(literal) == Literal(
            atom=Atom("p", (Function("f", (symbols["a"],)),)),
            polarity=True,
        )

    def test_unify_tableau_variable_keys_directly(self, symbols):
        sub = TermSubstitution()
        source = Variable("X", vid=1)
        older = (1, source)
        newer = (2, source)

        ok, bindings = sub.unify(older=older, newer=newer)

        assert ok is True
        assert bindings == (binding(newer, source, 1),)
        sub.bind(bindings)
        assert sub.to_dict()[newer] == TableauVariable(instance_id=1, source=source)

    def test_tableau_variable_keys_preserve_clause_instance_scope(self, symbols):
        sub = TermSubstitution()
        source = Variable("X", vid=1)
        literal = Literal(atom=Atom("p", (source,)), polarity=True)

        assert sub.unify_literals(
            older=literal,
            older_instance=1,
            newer=literal,
            newer_instance=2,
        ) == (
            True,
            (binding((2, source), source, 1),),
        )
