from connections.calculi.intuitionistic import *
from connections.utils.primitives import *


class S5ConnectionState(IConnectionState):
    
    def __init__(self, matrix, domain, iterative_deepening=False):
        super().__init__(matrix, iterative_deepening)
        self.domain = domain

    # always append variable W to prefix of negated literal (polarity 1)
    def _pre_eq(self,lit_1,lit_2):
        if lit_2.prefix is None:
            lit_2.prefix = Function('string')
        if lit_1.prefix is None:
            lit_1.prefix = Function('string')
        pre_1 = Function('string',args=lit_1.prefix.args[-1:])
        pre_2 = Function('string',args=lit_2.prefix.args[-1:])
        return pre_1, pre_2


    # single prefix subsitution for all pairs (var,eigenvar) in classical substitution and (lit,lit) in classical connections
    def _admissible_pairs(self):
        if self.domain in ['constant','cumulative']:
            return []
        if self.domain == 'varying':
            equations = []
            for var, term in self.substitutions[-1].items():
            # loop over eigenvariables (given by "f_skolem" symbol)
                for eigen in self._find_eigenvariables(term):
                    pre_1 = Function('string',args=var.prefix.args[-1:])
                    pre_2 = Function('string',args=eigen.prefix.args[-1:])
                    equations.append((pre_1, pre_2))
            return equations