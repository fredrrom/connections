from cops.calculi.intuitionistic import *
from cops.utils.primitives import *
import cops.utils.unification_d as d


class DConnectionState(IConnectionState):

    def __init__(self, matrix, domain):
        super().__init__(matrix)
        self.domain = domain

    def pre_unify(self,pre_1,pre_2,s):
        return d.pre_unify(pre_1.args, [], pre_2.args, s=s)
    
    def pre_unify_list(self,list,s):
        return d.pre_unify_list(list,s)

    # Don't append W
    def _pre_eq(self,lit_1,lit_2):
        if lit_2.prefix is None:
            lit_2.prefix = Function('string')
        if lit_1.prefix is None:
            lit_1.prefix = Function('string')
        pre_1, pre_2 = lit_1.prefix, lit_2.prefix
        return pre_1, pre_2


    # single prefix subsitution for all pairs (var,eigenvar) in classical substitution and (lit,lit) in classical connections
    def _admissible_pairs(self):
        if self.domain in 'constant':
            return []
        if self.domain == 'cumulative':
            equations = []
            for var, term in self.substitutions[-1].items():
                # loop over eigenvariables (given by "f_skolem" symbol)
                for eigen in self._find_eigenvariables(term):
                    var_pre = Function('string',var.prefix.args[:len(eigen.prefix.args)])
                    equations.append((var_pre, eigen.prefix))
            return equations
        if self.domain == 'varying':
            equations = []
            for var, term in self.substitutions[-1].items():
            # loop over eigenvariables (given by "f_skolem" symbol)
                for eigen in self._find_eigenvariables(term):
                    equations.append((var.prefix, eigen.prefix))
            return equations