from connections.calculi.classical import *
from connections.utils.primitives import *
from connections.utils.unification_intu import pre_unify, pre_unify_list


class IConnectionState(ConnectionState):

    def __init__(self, matrix, settings):
        super().__init__(matrix, settings)
        self.prefix_unifier = {}
        self.var_gen_num = 0

    def pre_unify(self,pre_1,pre_2,s):
        return pre_unify(pre_1.args, [], pre_2.args, s=s)
    
    def pre_unify_list(self,list,s):
        return pre_unify_list(list,s)

    def append_fresh_var(self, string):
        self.var_gen_num += 1
        return Function(string.symbol, string.args + [Variable("W"+str(self.var_gen_num))])
    

    # always append variable W to prefix of negated literal (polarity 1)
    def _pre_eq(self,lit_1,lit_2):
        if not lit_1.neg:
            lit_1, lit_2 = lit_2, lit_1 
        if lit_2.prefix is None:
            lit_2.prefix = Function('string')
        if lit_1.prefix is None:
            lit_1.prefix = Function('string')
        pre_1, pre_2 = self.append_fresh_var(lit_1.prefix), lit_2.prefix
        return pre_1, pre_2


    def _extensions(self):
        ret = []
        for ex in super()._extensions():
            lit_1 = self.goal.literal
            lit_2 = ex.clause_copy[ex.lit_idx]
            pre_1, pre_2 = self._pre_eq(lit_1, lit_2)
            self.substitution.update(ex.sub_updates)
            if self.pre_unify(pre_1, pre_2, self.substitution) is not None:
                ret.append(ex)
            self.substitution.backtrack()
        return ret

    def _reductions(self):
        ret = []
        for re in super()._reductions():
            lit_1 = self.goal.literal
            lit_2 = re.path_lit
            pre_1, pre_2 = self._pre_eq(lit_1, lit_2)
            self.substitution.update(re.sub_updates)
            if self.pre_unify(pre_1, pre_2, self.substitution) is not None:
                ret.append(re)
            self.substitution.backtrack()
        return ret


    # add check for syntactically equal prefixes
    def _regularizable(self, clause):
        for path_lit in self.goal.path():
            for clause_lit in clause:
                if path_lit.neg == clause_lit.neg and path_lit.symbol == clause_lit.symbol:
                    if self.substitution.equal(path_lit, clause_lit):
                        if self.substitution.equal(path_lit.prefix, clause_lit.prefix):
                            return True
        return False

    def _find_eigenvariables(self, term):
        if term.symbol == 'f_skolem':
            return [term]
        if isinstance(term, Function):
            return [eigen for subterm in term.args for eigen in self._find_eigenvariables(subterm)]
        return []

    # single prefix subsitution for all pairs (var,eigenvar) in classical substitution and (lit,lit) in classical connections
    def _admissible_pairs(self):
        equations = []
        for var, term in self.substitution.to_dict().items():
            # loop over eigenvariables (given by "f_skolem" symbol)
            for eigen in self._find_eigenvariables(term):
                if var.prefix is None:
                    var.prefix = Function('string')
                if eigen.prefix is None:
                    var.prefix = Function('string')
                equations.append((var.prefix, self.append_fresh_var(eigen.prefix)))
        return equations
    
    def _proof_pairs(self):
        equations = []
        # Loop over actions to find all literal connections
        for action in self.proof_sequence:
            if action.type in ['st','bt']:
                continue
            lit_1 = action.principle_node.literal
            if action.type == "re":
                lit_2 = action.path_lit
            else:
                lit_2 = action.clause_copy[action.lit_idx]
            equations.append(self._pre_eq(lit_1, lit_2))
        return equations

    def theorem_or_next(self):
        new_goal = self.goal.find_next()
        if new_goal is not None:
            # Not classical proof, keep going new goal
            self.goal = new_goal
            self.goal.actions = self._legal_actions()
            return
        # Classical proof, check intutitionistic proof
        addco_pairs = self._admissible_pairs()
        proof_pairs = self._proof_pairs()
        print(f'prefix_unify({[(self.substitution(l),self.substitution(r)) for l,r in addco_pairs + proof_pairs]})')
        s = self.pre_unify_list(addco_pairs + proof_pairs, self.substitution)
        if s is not None:
            # Intuitonistic proof, return success
            self.info = 'Theorem'
            self.prefix_unifier = s
            self.is_terminal = True
            return
        """
        uncomment to do comparisons
        print('prefix_unify_success')
        print(f'successful_connections:{len(self.proof_sequence)}')
        print(f'prefix_unify({[(flatten(subst(s,l)),flatten(subst(s,r))) for l,r in addco_pairs + proof_pairs]})')
        """
        # No intuitionistic proof, keep going from current goal
        self.proof_sequence.pop()
        self.substitution.backtrack()
        self.goal.children = []
        parent = self.goal
        while parent is not None:
            parent.proven = False
            parent = parent.parent