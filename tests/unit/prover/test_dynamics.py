from connections.syntax.formula import Atom, Function, Prefix, Variable
from connections.syntax.matrix import Clause, Literal, Matrix
from connections.prover.actions import ApplyAction, UndoAction
from connections.prover.dynamics import Dynamics
from connections.prover.rules import (
    Extension,
    Reduction,
    Start,
)
from connections.prover.prover import Problem
from connections.prover.state import State
from connections.prover.tableau import Tableau


def lit(name: str, *args, neg: bool = False) -> Literal:
    return Literal(atom=Atom(name, args), polarity=not neg)


def literal_symbol(state: State, goal_id: int) -> str:
    literal = state.source_literal_at(goal_id)
    assert literal is not None
    return literal.atom.symbol


def literal_arg(state: State, goal_id: int, index: int = 0):
    literal = state.source_literal_at(goal_id)
    assert literal is not None
    return literal.atom.args[index]


def scoped_literal_arg(state: State, goal_id: int, index: int = 0):
    context = state.literal_context_at(goal_id)
    assert context is not None
    literal, instance_id = context
    variable = literal.atom.args[index]
    return variable if instance_id is None else (instance_id, variable)


def scoped_literal_ref(state: State, goal_id: int, index: int = 0):
    context = state.literal_context_at(goal_id)
    assert context is not None
    literal, instance_id = context
    return literal.atom.args[index], instance_id


def scoped_rule_literal_arg(rule, index: int = 0):
    variable = rule.clause.literal(index).atom.args[0]
    return variable if rule.instance_id is None else (rule.instance_id, variable)


def binding(variable, target, instance_id=None):
    return variable, (target, instance_id)


def _state_for(matrix: Matrix) -> State:
    problem = Problem(matrix=matrix, start_clauses="positive")
    tableau = Tableau()
    return State(problem, tableau)


def apply_rule(state: State, parent_goal_id: int, rule):
    return state.apply_rule(
        parent_goal_id=parent_goal_id,
        rule=rule,
    )


def test_dynamics_exposes_structured_goal_and_proof_step_views():
    state = _state_for(
        Matrix(
            (
                Clause((lit("p"), lit("q"))),
                Clause((lit("p", neg=True),)),
                Clause((lit("q", neg=True),)),
            )
        )
    )
    tableau = state.tableau
    dynamics = Dynamics

    assert tuple(goal.goal_id for goal in state.fringe) == (tableau.root_goal_id,)
    assert tuple(tableau.rule_applications) == ()

    start = dynamics.apply_actions(state, tableau.root).start[0]
    assert isinstance(start, ApplyAction)

    dynamics.transition(state, start)

    assert [literal_symbol(state, goal.goal_id) for goal in state.fringe] == [
        "p",
        "q",
    ]
    assert len(tableau.rule_applications) == 1
    assert (
        tableau.rule_applications[
            next(iter(tableau.rule_applications))
        ].rule.__class__.__name__.lower()
        == "start"
    )
    assert isinstance(dynamics.get_undo(state, tableau.root), UndoAction)


def test_dynamics_orders_goal_actions_before_undo():
    state = _state_for(
        Matrix(
            (
                Clause((lit("p"), lit("q"))),
                Clause((lit("p", neg=True),)),
                Clause((lit("q", neg=True),)),
            )
        )
    )
    tableau = state.tableau
    dynamics = Dynamics
    dynamics.transition(state, dynamics.apply_actions(state, tableau.root).start[0])

    goal = state.fringe[0]
    actions = [*dynamics.apply_actions(state, goal).ordered()]
    undo = dynamics.get_undo(state, tableau.root)
    assert undo is not None
    actions.append(undo)

    assert [
        action.rule.__class__.__name__.lower()
        if isinstance(action, ApplyAction)
        else "undo"
        for action in actions
    ] == ["extension", "undo"]
    assert actions[0] == dynamics.apply_actions(state, goal).extension[0]
    assert actions[-1] == undo


def test_dynamics_can_be_constructed_directly_from_problem_and_tableau():
    state = _state_for(
        Matrix(
            (
                Clause((lit("p"), lit("q"))),
                Clause((lit("p", neg=True),)),
                Clause((lit("q", neg=True),)),
            )
        )
    )
    dynamics = Dynamics

    assert len(dynamics.apply_actions(state, state.tableau.root).start) == 1


def test_transition_with_no_action_returns_same_state():
    state = _state_for(Matrix((Clause((lit("p"),)),)))

    assert Dynamics.transition(state, None) is state


def test_dynamics_returns_no_apply_actions_for_regularizable_goal():
    state = _state_for(
        Matrix(
            (
                Clause((lit("p"),)),
                Clause((lit("p", neg=True), lit("q"))),
                Clause((lit("q", neg=True), lit("q"), lit("r"))),
            )
        )
    )
    tableau = state.tableau
    dynamics = Dynamics
    dynamics.transition(state, dynamics.apply_actions(state, tableau.root).start[0])
    dynamics.transition(
        state, dynamics.apply_actions(state, state.fringe[0]).extension[0]
    )
    dynamics.transition(
        state, dynamics.apply_actions(state, state.fringe[0]).extension[0]
    )

    assert [literal_symbol(state, goal.goal_id) for goal in state.fringe] == [
        "q",
        "r",
    ]
    assert not dynamics.apply_actions(state, state.fringe[1])


def test_regularity_ignores_consumed_extension_literal():
    state = State(
        Problem(matrix=Matrix((Clause((lit("dummy"),)),)), start_clauses="positive"),
        Tableau(),
    )
    tableau = state.tableau
    start = apply_rule(state, tableau.root_goal_id, Start(Clause((lit("p"),))))
    (p_goal_id,) = start.child_goal_ids
    first_extension = apply_rule(
        state,
        p_goal_id,
        Extension(lit_idx=0, clause=Clause((lit("p", neg=True), lit("p", neg=True)))),
    )
    (negative_p_goal_id,) = first_extension.child_goal_ids
    second_extension = apply_rule(
        state,
        negative_p_goal_id,
        Extension(lit_idx=0, clause=Clause((lit("p"), lit("q")))),
    )
    (q_goal_id,) = second_extension.child_goal_ids

    assert Dynamics.is_regular(state, tableau.goals[q_goal_id])


def test_regularity_ignores_closed_sibling_literals():
    state = State(
        Problem(matrix=Matrix((Clause((lit("dummy"),)),)), start_clauses="positive"),
        Tableau(),
    )
    tableau = state.tableau
    start = apply_rule(state, tableau.root_goal_id, Start(Clause((lit("q"),))))
    (path_goal_id,) = start.child_goal_ids
    extension = apply_rule(
        state,
        path_goal_id,
        Extension(lit_idx=0, clause=Clause((lit("q", neg=True), lit("q"), lit("r")))),
    )
    left_goal_id, right_goal_id = extension.child_goal_ids

    assert not Dynamics.is_regular(state, tableau.goals[right_goal_id])

    apply_rule(state, left_goal_id, Reduction(source_goal_id=path_goal_id))

    assert Dynamics.is_regular(state, tableau.goals[right_goal_id])


def test_extension_constraint_delta_binds_new_clause_variables_to_older_goal_variables():
    x_var = Variable("X", vid=1)
    y_var = Variable("Y", vid=2)
    state = _state_for(
        Matrix(
            (
                Clause((lit("p", x_var),)),
                Clause((lit("p", y_var, neg=True),)),
            )
        )
    )
    tableau = state.tableau
    dynamics = Dynamics
    dynamics.transition(state, dynamics.apply_actions(state, tableau.root).start[0])

    goal_id = state.fringe[0].goal_id
    extension = dynamics.apply_actions(state, tableau.goals[goal_id]).extension[0]
    clause_var = scoped_rule_literal_arg(extension.rule)

    assert extension.rule.constraint_delta.term_bindings == (
        binding(clause_var, *scoped_literal_ref(state, goal_id)),
    )


def test_start_rule_carries_clause_free_variables():
    free_variable = Variable("X", prefix=Prefix((Function("w"),)))
    state = _state_for(
        Matrix((Clause((lit("p", free_variable),), free_variables=(free_variable,)),))
    )
    start = Dynamics.apply_actions(state, state.tableau.root).start[0]

    assert start.rule.constraint_delta.free_variables == (
        (free_variable, start.rule.instance_id),
    )

    Dynamics.transition(state, start)

    assert state.constraints.free_variables == (
        (free_variable, start.rule.instance_id),
    )


def test_extension_rule_carries_clause_free_variables():
    free_variable = Variable("X", prefix=Prefix((Function("w"),)))
    state = _state_for(
        Matrix(
            (
                Clause((lit("p", Variable("Y")),)),
                Clause(
                    (lit("p", Variable("X"), neg=True),),
                    free_variables=(free_variable,),
                ),
            )
        )
    )
    Dynamics.transition(
        state, Dynamics.apply_actions(state, state.tableau.root).start[0]
    )

    goal = state.fringe[0]
    extension = Dynamics.apply_actions(state, goal).extension[0]

    assert extension.rule.constraint_delta.free_variables == (
        (free_variable, extension.rule.instance_id),
    )

    Dynamics.transition(state, extension)

    assert state.constraints.free_variables == (
        (free_variable, extension.rule.instance_id),
    )


def test_start_rule_rejects_inadmissible_free_variables():
    first = Variable("X", prefix=Prefix((Function("a"),)))
    second = Variable("X", prefix=Prefix((Function("b"),)))
    state = State(
        Problem(
            matrix=Matrix(
                (
                    Clause(
                        (lit("p", Variable("X")),),
                        free_variables=(first, second),
                    ),
                )
            ),
            start_clauses="positive",
            logic="D",
            domain="varying",
        ),
        Tableau(),
    )

    assert Dynamics.apply_actions(state, state.tableau.root).start == ()


def test_extension_rule_rejects_inadmissible_free_variables():
    free_variable = Variable("X", prefix=Prefix((Function("a"),)))
    state = State(
        Problem(
            matrix=Matrix(
                (
                    Clause(
                        (
                            lit(
                                "p",
                                Function(
                                    "sk",
                                    prefix=Prefix((Function("a"), Function("b"))),
                                ),
                            ),
                        )
                    ),
                    Clause(
                        (lit("p", Variable("X"), neg=True),),
                        free_variables=(free_variable,),
                    ),
                )
            ),
            start_clauses="positive",
            logic="D",
            domain="cumulative",
        ),
        Tableau(),
    )
    Dynamics.transition(
        state, Dynamics.apply_actions(state, state.tableau.root).start[0]
    )

    assert Dynamics.apply_actions(state, state.fringe[0]).extension == ()


def test_undo_removes_bindings_owned_by_removed_rule_application():
    x_var = Variable("X", vid=1)
    y_var = Variable("Y", vid=2)
    state = _state_for(
        Matrix(
            (
                Clause((lit("p", x_var),)),
                Clause((lit("p", y_var, neg=True),)),
            )
        )
    )
    dynamics = Dynamics
    dynamics.transition(
        state, dynamics.apply_actions(state, state.tableau.root).start[0]
    )
    goal_id = state.fringe[0].goal_id
    extension = dynamics.apply_actions(state, state.tableau.goals[goal_id]).extension[0]

    dynamics.transition(state, extension)
    assert state.constraints.term_bindings

    undo = dynamics.get_undo(state, state.tableau.goals[goal_id])
    assert undo is not None
    dynamics.transition(state, undo)

    assert state.constraints.term_bindings == {}


def test_extension_rules_use_source_clause_instances():
    x_var = Variable("X", vid=1)
    y_var = Variable("Y", vid=2)
    state = _state_for(
        Matrix(
            (
                Clause((lit("p", x_var),)),
                Clause((lit("p", y_var, neg=True), lit("q", y_var))),
            )
        )
    )
    dynamics = Dynamics
    dynamics.transition(
        state, dynamics.apply_actions(state, state.tableau.root).start[0]
    )
    goal_id = state.fringe[0].goal_id

    extension = dynamics.apply_actions(state, state.tableau.goals[goal_id]).extension[0]

    assert extension.rule.clause is state.problem.matrix.clauses[1]
    assert extension.rule.clause_idx == 1
    assert extension.rule.instance_id is not None
    selected_var = scoped_rule_literal_arg(extension.rule, 0)
    sibling_var = scoped_rule_literal_arg(extension.rule, 1)
    assert selected_var == sibling_var
    assert extension.rule.constraint_delta.term_bindings == (
        binding(selected_var, *scoped_literal_ref(state, goal_id)),
    )


def test_reduction_constraint_delta_binds_new_goal_variables_to_older_path_variables():
    x_var = Variable("X", vid=1)
    u_var = Variable("U", vid=2)
    v_var = Variable("V", vid=3)

    state = State(
        Problem(matrix=Matrix((Clause((lit("dummy"),)),)), start_clauses="positive"),
        Tableau(),
    )
    tableau = state.tableau
    start = apply_rule(
        state,
        tableau.root_goal_id,
        Start(Clause((lit("p", x_var, neg=True), lit("q")))),
    )
    path_goal_id, _sibling_goal_id = start.child_goal_ids
    extension = apply_rule(
        state,
        path_goal_id,
        Extension(lit_idx=0, clause=Clause((lit("p", u_var), lit("p", v_var)))),
    )
    (current_goal_id,) = extension.child_goal_ids

    path_var = literal_arg(state, path_goal_id)
    current_var = literal_arg(state, current_goal_id)
    dynamics = Dynamics
    reduction = dynamics.apply_actions(state, tableau.goals[current_goal_id]).reduction[
        0
    ]

    assert reduction.rule.constraint_delta.term_bindings == (
        binding(current_var, path_var),
    )


def test_factorization_sources_from_closed_siblings_on_path_only():
    state = State(
        Problem(matrix=Matrix((Clause((lit("dummy"),)),)), start_clauses="positive"),
        Tableau(),
    )
    tableau = state.tableau
    root = apply_rule(state, tableau.root_goal_id, Start(Clause((lit("p"), lit("q")))))
    closed_goal_id, open_goal_id = root.child_goal_ids

    apply_rule(state, closed_goal_id, Reduction(source_goal_id=tableau.root_goal_id))
    open_step = apply_rule(
        state,
        open_goal_id,
        Extension(lit_idx=0, clause=Clause((lit("q", neg=True), lit("p")))),
    )
    (target_goal_id,) = open_step.child_goal_ids

    assert tableau.goals[open_goal_id].factorization_source_goal_ids_by_signed_symbol[
        lit("p").signed_symbol
    ] == (closed_goal_id,)
    assert (
        lit("p").signed_symbol
        not in tableau.goals[
            target_goal_id
        ].factorization_source_goal_ids_by_signed_symbol
    )
    assert state.current_path_factorization_source_goal_ids_for(
        target_goal_id, lit("p").signed_symbol
    ) == (closed_goal_id,)

    dynamics = Dynamics
    factorization_actions = dynamics.apply_actions(
        state, tableau.goals[target_goal_id]
    ).factorization

    assert len(factorization_actions) == 1
    assert factorization_actions[0].rule.source_goal_id == closed_goal_id
    assert factorization_actions[0].rule.mode == "unify"
    assert (
        str(factorization_actions[0]) == f"factorization(source_goal={closed_goal_id})"
    )

    lemma_actions = dynamics.apply_actions(
        state, tableau.goals[target_goal_id], factorization="equal"
    ).factorization

    assert len(lemma_actions) == 1
    assert lemma_actions[0].rule.source_goal_id == closed_goal_id
    assert lemma_actions[0].rule.mode == "equal"
    assert lemma_actions[0].rule.constraint_delta.term_bindings == ()
    assert str(lemma_actions[0]) == f"lemma(source_goal={closed_goal_id})"
    Dynamics.transition(state, lemma_actions[0])
    assert tableau.goals[target_goal_id].closed is True


def test_factorization_constraint_delta_binds_new_goal_variables_to_closed_source_variables():
    x_var = Variable("X", vid=1)
    y_var = Variable("Y", vid=2)
    state = State(
        Problem(matrix=Matrix((Clause((lit("dummy"),)),)), start_clauses="positive"),
        Tableau(),
    )
    tableau = state.tableau
    root = apply_rule(
        state, tableau.root_goal_id, Start(Clause((lit("p", x_var), lit("q"))))
    )
    closed_goal_id, open_goal_id = root.child_goal_ids

    apply_rule(state, closed_goal_id, Reduction(source_goal_id=tableau.root_goal_id))
    open_step = apply_rule(
        state,
        open_goal_id,
        Extension(lit_idx=0, clause=Clause((lit("q", neg=True), lit("p", y_var)))),
    )
    (target_goal_id,) = open_step.child_goal_ids

    source_var = literal_arg(state, closed_goal_id)
    target_var = literal_arg(state, target_goal_id)
    factorization = Dynamics.apply_actions(
        state, tableau.goals[target_goal_id]
    ).factorization[0]

    lemma_actions = Dynamics.apply_actions(
        state, tableau.goals[target_goal_id], factorization="equal"
    ).factorization

    assert factorization.rule.constraint_delta.term_bindings == (
        binding(target_var, source_var),
    )
    assert factorization.rule.mode == "unify"
    assert lemma_actions == ()
