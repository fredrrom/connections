from cops.calculi.classical import ConnectionEnv
from cops.utils.icnf_parsing import file2cnf

class MConnectionEnv(ConnectionEnv):

    def __init__(self, path, logic='S4', domain='cumulative'):
        self.matrix = file2cnf(path)
        self.logic = logic
        self.domain = domain
        self._init_state()

    def _init_state(self):
        if self.logic == 'D':
            from cops.calculi.modal_d import DConnectionState
            self.state = DConnectionState(self.matrix, self.domain)
        elif self.logic == 'T':
            from cops.calculi.modal_t import TConnectionState
            self.state = TConnectionState(self.matrix, self.domain)
        elif self.logic == 'S4':
            from cops.calculi.modal_s4 import S4ConnectionState
            self.state = S4ConnectionState(self.matrix, self.domain)
        elif self.logic == 'S5':
            from cops.calculi.modal_s5 import S5ConnectionState
            self.state = S5ConnectionState(self.matrix, self.domain)

    def reset(self):
        self.matrix.reset()
        self._init_state()
        self.state.reset()
        return self.state