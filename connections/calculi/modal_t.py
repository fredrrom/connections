from connections.calculi.intuitionistic import *
from connections.utils.primitives import *
import connections.utils.unification_t as t


class TConnectionState(IConnectionState):

    def pre_unify(self,pre_1,pre_2,s):
        return t.pre_unify(pre_1.args, [], pre_2.args, s=s)
    
    def pre_unify_list(self,list,s):
        return t.pre_unify_list(list,s)

    def _pre_eq(self,lit_1,lit_2):
        if lit_2.prefix is None:
            lit_2.prefix = Function('string')
        if lit_1.prefix is None:
            lit_1.prefix = Function('string')
        pre_1, pre_2 = lit_1.prefix, lit_2.prefix
        return pre_1, pre_2

    def _admissible_pairs(self):
        if self.settings.domain in 'constant':
            return []
        if self.settings.domain == 'cumulative':
            equations = []
            for var, term in self.substitutions[-1].items():
                # loop over eigenvariables (given by "f_skolem" symbol)
                for eigen in self._find_eigenvariables(term):
                    var_pre = Function('string',var.prefix.args[:len(eigen.prefix.args)])
                    equations.append((var_pre, eigen.prefix))
            return equations
        if self.settings.domain == 'varying':
            equations = []
            for var, term in self.substitutions[-1].items():
            # loop over eigenvariables (given by "f_skolem" symbol)
                for eigen in self._find_eigenvariables(term):
                    equations.append((var.prefix, eigen.prefix))
            return equations