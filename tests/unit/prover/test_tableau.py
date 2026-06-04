from connections.core.formula import Atom
from connections.core.matrix import Clause, Literal, Matrix
from connections.prover.state import State
from connections.prover.prover import Problem
from connections.prover.rules import Extension, Reduction, Start
from connections.prover.tableau import Tableau


def lit(name: str, *, neg: bool = False) -> Literal:
    return Literal(atom=Atom(name), polarity=not neg)


def state() -> State:
    return State(
        Problem(matrix=Matrix((Clause((lit("dummy"),)),)), start_clauses="positive"),
        Tableau(),
    )


def apply_rule(proof_state: State, parent_goal_id: int, rule):
    return proof_state.apply_rule(
        parent_goal_id=parent_goal_id,
        rule=rule,
    )


def test_tableau_reset_starts_with_root_goal():
    tableau = Tableau()

    assert tableau.root.goal_id == tableau.root_goal_id
    assert tableau.root.closed is False


def test_start_application_replaces_root_goal_with_child_goals():
    proof_state = state()
    step = apply_rule(
        proof_state,
        proof_state.tableau.root.goal_id,
        Start(Clause((lit("p"), lit("q")))),
    )

    literal_symbols = []
    for goal_id in (goal.goal_id for goal in proof_state.fringe):
        literal = proof_state.source_literal_at(goal_id)
        assert literal is not None
        literal_symbols.append(literal.atom.symbol)
    assert literal_symbols == ["p", "q"]
    assert [
        rule_application.rule.__class__.__name__.lower()
        for rule_application in proof_state.tableau.rule_applications.values()
    ] == ["start"]
    assert step.child_goal_ids == tuple(goal.goal_id for goal in proof_state.fringe)


def test_extension_application_marks_theorem_when_last_goal_closes():
    proof_state = state()
    start = apply_rule(
        proof_state, proof_state.tableau.root.goal_id, Start(Clause((lit("p"),)))
    )
    goal_id = start.child_goal_ids[0]
    apply_rule(
        proof_state, goal_id, Extension(lit_idx=0, clause=Clause((lit("p", neg=True),)))
    )

    assert proof_state.fringe == []
    assert proof_state.tableau.goals[goal_id].closed is True
    assert proof_state.tableau.root.closed is True


def test_node_indices_follow_committed_tree():
    proof_state = state()
    start = apply_rule(
        proof_state,
        proof_state.tableau.root.goal_id,
        Start(Clause((lit("p"), lit("q")))),
    )
    goal_p_id, goal_q_id = start.child_goal_ids

    assert proof_state.tableau.goals[proof_state.tableau.root_goal_id].address == ()
    assert proof_state.tableau.goals[goal_p_id].address == (0,)
    assert proof_state.tableau.goals[goal_q_id].address == (1,)
    assert proof_state.path_goal_ids_for(goal_p_id, lit("p").signed_symbol) == ()
    assert proof_state.tableau.rule_applications[
        start.rule_application_id
    ].child_goal_ids == (goal_p_id, goal_q_id)
    sibling_literal = proof_state.source_literal_at(goal_q_id)
    assert sibling_literal is not None
    assert sibling_literal.atom.symbol == "q"


def test_undo_reinserts_closed_subtree_parent_by_stable_address():
    proof_state = state()
    start = apply_rule(
        proof_state,
        proof_state.tableau.root.goal_id,
        Start(Clause((lit("p"), lit("q")))),
    )
    goal_p_id, goal_q_id = start.child_goal_ids
    closed = apply_rule(
        proof_state,
        goal_p_id,
        Reduction(source_goal_id=proof_state.tableau.root_goal_id),
    )

    assert [goal.goal_id for goal in proof_state.fringe] == [goal_q_id]

    proof_state.undo_rule_application(closed.rule_application_id)

    assert [goal.goal_id for goal in proof_state.fringe] == [goal_p_id, goal_q_id]


def test_literal_resolution_prefers_rule_application_clause_when_index_is_present():
    tableau = Tableau()
    step = tableau.add_rule_application(
        parent_goal_id=tableau.root.goal_id,
        rule=Start(Clause((lit("p"), lit("q")))),
        child_literal_indices=(0, 1),
    )
    goal_id = step.child_goal_ids[0]
    tableau.goals[goal_id].literal_index = 1

    assert tableau.source_literal_at(goal_id) == lit("q")


def test_root_has_no_literal():
    tableau = Tableau()

    assert tableau.source_literal_at(tableau.root_goal_id) is None
