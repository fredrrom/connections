from connections.core.formula import Variable
from connections.constraints.term import TableauVariable


def test_tableau_variables_reuse_scope_within_clause_occurrence():
    original = Variable("X", vid=1)

    first = TableauVariable(instance_id=1, source=original)
    second = TableauVariable(instance_id=1, source=original)

    assert first == second
    assert first.source == original


def test_tableau_variables_do_not_share_scope_across_clause_occurrences():
    original = Variable("X", vid=1)

    first = TableauVariable(instance_id=1, source=original)
    second = TableauVariable(instance_id=2, source=original)

    assert first != second
    assert first.source == original
    assert second.source == original
