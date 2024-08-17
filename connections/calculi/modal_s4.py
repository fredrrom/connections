from connections.calculi.intuitionistic import *
from connections.utils.primitives import *


class S4ConnectionState(IConnectionState):

    # No append W otherwise same as intu?
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
            return super()._admissible_pairs()
        if self.settings.domain == 'varying':
            equations = []
            for var, term in self.substitution.to_dict().items():
            # loop over eigenvariables (given by "f_skolem" symbol)
                for eigen in self._find_eigenvariables(term):
                    equations.append((var.prefix, eigen.prefix))
            return equations