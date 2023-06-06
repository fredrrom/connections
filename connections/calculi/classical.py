from connections.utils.unification import unify, subst
from connections.utils.cnf_parsing import file2cnf


class Tableau:
    def __init__(self, literal=None, parent=None):
        self.literal = literal
        self.parent = parent
        self.children = []
        self.proven = False
        self.depth = parent.depth + 1 if parent is not None else 0
        self.actions = {}

    def __str__(self):
        ret = "\t" * self.depth + str(self.literal)
        for child in self.children:
            ret += "\n" + str(child)
        return ret

    def path(self):
        path = []
        current = self.parent
        while current.literal is not None:
            path.append(current.literal)
            current = current.parent
        return path

    def find_next(self):
        parent = self
        while parent is not None:
            for child in parent.children:
                if not child.proven:
                    return child
            parent.proven = True
            parent = parent.parent
        return None

    def find_prev(self):
        parent = self.parent
        self_idx = parent.children.index(self)
        if self_idx > 1 or (self_idx == 1 and parent.literal is None):
            self.actions = {}
            prev = parent.children[self_idx - 1]
            while len(prev.children) > 1:
                prev = prev.children[-1]
        else:
            prev = parent
        prev.proven = False
        return prev


class ConnectionState:
    
    def __init__(self, matrix):
        # Matrix fields
        self.matrix = matrix
        self.start_idx = 0

        # Tableau fields
        self.tableau = None
        self.goal = None
        self.max_depth = None
        self.termination_depth = float("inf")

        # Proof fields
        self.info = None
        self.is_terminal = False
        self.qed = False
        self.proof_sequence = []
        self.substitutions = [dict()]

    @property
    def substitution(self):
        return self.substitutions[-1]

    def _next_start_clause(self):
        self.start_idx += 1
        if self.start_idx >= len(self.matrix.positive_clauses):
            self.max_depth += 1
            self.start_idx = 0
        self.reset(idx=self.start_idx, depth=self.max_depth)

    def reset(self, idx=0, depth=2):
        self.start_idx = idx
        self.max_depth = depth
        if len(self.matrix.positive_clauses) > 0:
            clause = self.matrix.copy(self.matrix.positive_clauses[self.start_idx])
            self.tableau = Tableau()
            self.tableau.children = [Tableau(lit, self.tableau) for lit in clause]
            self.goal = self.tableau.children[0]
            self.goal.actions = self._legal_actions()
        else:
            self.info = 'Non-Theorem, no positive start clauses'
            self.is_terminal = True
            self.qed = True

    def _extensions(self):
        extensions = []
        for clause_idx, lit_idx in self.matrix.complements(self.goal.literal):
            clause_copy = self.matrix.copy(clause_idx)
            sigma = unify(
                self.goal.literal,
                clause_copy[lit_idx],
                self.substitutions[-1],
            )
            if sigma is not None:
                extensions.append(
                    ConnectionAction(
                        inference_type="ex",
                        principle_node=self.goal,
                        sigma=sigma,
                        lit_idx=lit_idx,
                        clause_copy=clause_copy,
                        id="ex" + str(len(extensions)),
                    )
                )
        return extensions

    def _reductions(self):
        reductions = []
        for lit in self.goal.path():
            sigma = None
            if self.goal.literal.neg != lit.neg and self.goal.literal.symbol == lit.symbol:
                sigma = unify(self.goal.literal, lit, self.substitutions[-1])
            if sigma is not None:
                reductions.append(
                    ConnectionAction(
                        inference_type="re",
                        principle_node=self.goal,
                        sigma=sigma,
                        path_lit=lit,
                        id="re" + str(len(reductions)),
                    )
                )
        return reductions

    def _regularizable(self, clause, sub):
        for path_lit in self.goal.path():
            for clause_lit in clause:
                if path_lit.neg == clause_lit.neg and path_lit.symbol == clause_lit.symbol:
                    if subst(sub, path_lit) == subst(sub, clause_lit):
                        return True
        return False

    def _legal_actions(self):
        current_clause = [node.literal for node in self.goal.parent.children[1:]]
        reg = self._regularizable(current_clause, self.substitutions[-1])
        if (self.goal is None) or reg:
            return {}
        if self.goal.depth >= self.max_depth:
            return {action.id: action for action in self._reductions()}
        actions = self._reductions() + self._extensions()
        return {action.id: action for action in actions}

    def backtrack(self):
        actions = []
        while not actions:
            # If no proof has been found before reaching the termination depth, terminate
            if self.max_depth > self.termination_depth:
                self.info = f'Depth limit exceeded ({self.termination_depth})'
                self.is_terminal = True
                break

            # Find non-attempted actions
            actions = self.goal.actions
            # If all actions have been tried, backtrack to previous goal
            if actions:
                continue

            self.goal = self.goal.find_prev()
            if self.proof_sequence:
                self.proof_sequence.pop()

            # If no new actions available for previous goals try next start clause or increase depth
            if self.goal and self.goal.literal is None:
                self._next_start_clause()
            else:
                self.substitutions.pop()
                self.goal.proven = False
                self.goal.children = []

    def update_goal(self, action):
        del self.goal.actions[action.id]
        self.proof_sequence.append(action)

        # Make literal extended to child and mark as proven for backtracking purposes
        if action.inference_type == "ex":
            self.goal.children = [Tableau(lit, self.goal) for lit in action.clause_copy]
            self.goal.children[action.lit_idx].proven = True
            self.goal.children.insert(0, self.goal.children.pop(action.lit_idx))

        # Find next goal node, if None, a proof has been found, otherwise backtrack
        self.theorem_or_backtrack()

    def theorem_or_backtrack(self):
        self.goal = self.goal.find_next()
        if self.goal is None:
            self.info = 'Theorem'
            self.is_terminal = True
            self.qed = True
            return
        self.goal.actions = self._legal_actions()
        self.backtrack()


class ConnectionAction:
    """
    Abstract action class defines functions required of an action in an
    action space defined by a problem searched by an agent.
    """

    def __init__(
            self,
            inference_type,
            principle_node,
            sigma,
            id,
            lit_idx=None,
            path_lit=None,
            clause_copy=None,
    ):
        self.inference_type = inference_type
        self.principle_node = principle_node
        self.sigma = sigma
        self.path_lit = path_lit
        self.lit_idx = lit_idx
        self.clause_copy = clause_copy
        self.id = id

    def __str__(self):
        if self.inference_type == "ex":
            return f"{self.id}: {str(self.principle_node.literal)} -> {str(self.clause_copy)}"
        else:
            return (
                f"{self.id}: {str(self.principle_node.literal)} <- {str(self.path_lit)}"
            )

    def __repr__(self):
        return str(self)


class ConnectionEnv:
    def __init__(self, path):
        self.matrix = file2cnf(path)
        self.state = ConnectionState(self.matrix)

    @property
    def action_space(self):
        if self.state.goal is None:
            return [None]
        actions = list(self.state.goal.actions.values())
        if not actions:
            return [None]
        return actions

    def step(self, action):
        if self.state.is_terminal:
            return self.state, int(self.state.qed), self.state.is_terminal, {"status": self.state.info}
        if action is not None:
            self.state.substitutions.append(action.sigma)
            self.state.update_goal(action)
        elif len(self.state.matrix.positive_clauses) > 0:
            self.state.backtrack()
        return self.state, int(self.state.qed), self.state.is_terminal, {"status": self.state.info}

    def reset(self):
        self.matrix.reset()
        self.state = ConnectionState(self.matrix)
        self.state.reset()
        return self.state
