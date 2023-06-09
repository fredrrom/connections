from connections.utils.unification import unify, subst
from connections.utils.cnf_parsing import file2cnf


class Tableau:
    def __init__(self, literal=None, parent=None):
        self.literal = literal
        self.parent = parent
        self.children = []
        self.proven = False
        self.depth = parent.depth + 1 if parent is not None else -1
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
            prev = parent.children[self_idx - 1]
            while len(prev.children) > 1:
                prev = prev.children[-1]
        else:
            prev = parent
        return prev


class ConnectionState:
    
    def __init__(self, matrix):
        self.matrix = matrix
        self.reset()

    @property
    def substitution(self):
        return self.substitutions[-1]
    
    def reset(self, depth=1):
        # Tableau fields
        self.max_depth = depth
        self.tableau = Tableau()
        self.goal = self.tableau
        self.goal.actions = self._legal_actions()

        # Proof fields
        self.info = None
        self.is_terminal = False
        self.proof_sequence = []
        self.substitutions = [dict()]

    def _starts(self):
        starts = []
        for clause in self.matrix.positive_clauses:
            clause_copy = self.matrix.copy(clause)
            starts.append(
                    ConnectionAction(
                        type="st",
                        clause_copy=clause_copy,
                        id="st" + str(len(starts))
                    )
                )
        if not starts:
            starts.append(ConnectionAction(type="st", id="st0"))
        return starts
    
    def _backtracks(self):
        return [ConnectionAction(type='bt', id='bt')]

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
                        type="ex",
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
                        type="re",
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
        if self.goal.parent == None:
            return {action.id: action for action in self._starts()}
        current_clause = [node.literal for node in self.goal.parent.children[1:]]
        reg = self._regularizable(current_clause, self.substitutions[-1])
        if (self.goal is None) or reg:
            actions = self._backtracks()
        elif self.goal.depth >= self.max_depth:
            actions = self._reductions() + self._backtracks()
        else:
            actions = self._reductions() + self._extensions() + self._backtracks()
        return {action.id: action for action in actions}

    def backtrack(self):
        actions = {}
        while not actions or (actions.keys() == ['bt']):
            self.goal = self.goal.find_prev()

            if self.proof_sequence:
                self.proof_sequence.pop()

            actions = self.goal.actions
            self.substitutions.pop()
            self.goal.proven = False
            self.goal.children = []

            # If no new actions available for previous goals increase depth
            if self.goal is self.tableau and not self.goal.actions:
                self.reset(depth=self.max_depth+1)
                break

    def update_goal(self, action):
        del self.goal.actions[action.id]

        if action.type == 'bt':
            self.backtrack()
            return
        else:
            self.substitutions.append(action.sigma)
            self.proof_sequence.append(action)

        if action.type == 'st':
            if action.clause_copy is None:
                self.info = 'Non-Theorem: no positive start clauses'
                self.is_terminal = True
                return
            self.goal.children = [Tableau(lit, self.goal) for lit in action.clause_copy]

        # Make literal extended to child and mark as proven for backtracking purposes
        if action.type == "ex":
            self.goal.children = [Tableau(lit, self.goal) for lit in action.clause_copy]
            self.goal.children[action.lit_idx].proven = True
            self.goal.children.insert(0, self.goal.children.pop(action.lit_idx))

        if action.type == "re":
            self.goal.proven = True

        # Find next goal node, if None, a proof has been found, otherwise backtrack
        self.theorem_or_next()

    def theorem_or_next(self):
        self.goal = self.goal.find_next()
        if self.goal is None:
            self.info = 'Theorem'
            self.is_terminal = True
            return
        self.goal.actions = self._legal_actions()

class ConnectionAction:
    """
    Abstract action class defines functions required of an action in an
    action space defined by a problem searched by an agent.
    """

    def __init__(
            self,
            type,
            principle_node=None,
            sigma={},
            id=None,
            lit_idx=None,
            path_lit=None,
            clause_copy=None,
    ):
        self.type = type
        self.principle_node = principle_node
        self.sigma = sigma
        self.path_lit = path_lit
        self.lit_idx = lit_idx
        self.clause_copy = clause_copy
        self.id = id

    def __str__(self):
        if self.type == "ex":
            return f"{self.id}: {str(self.principle_node.literal)} -> {str(self.clause_copy)}"
        if self.type == "re":
            return f"{self.id}: {str(self.principle_node.literal)} <- {str(self.path_lit)}"
        if self.type == "st":
            return f"{self.id}: {str(self.clause_copy)}"
        if self.type == "bt":
            return 'Backtrack'

    def __repr__(self):
        return str(self)


class ConnectionEnv:
    def __init__(self, path):
        self.matrix = file2cnf(path)
        self.state = ConnectionState(self.matrix)

    @property
    def action_space(self):
        if self.goal is None:
            return [None]
        actions = list(self.state.goal.actions.values())
        return actions

    def step(self, action):
        if self.state.is_terminal:
            return self.state, int(self.state.is_terminal), self.state.is_terminal, {"status": self.state.info}
        else:
            self.state.update_goal(action)
        return self.state, int(self.state.is_terminal), self.state.is_terminal, {"status": self.state.info}

    def reset(self):
        self.matrix.reset()
        self.state = ConnectionState(self.matrix)
        self.state.reset()
        return self.state
