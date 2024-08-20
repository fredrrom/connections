from dataclasses import dataclass
from typing import Optional, Literal

LogicType = Literal['classical','intuitionistic','D','T','S4','S5']
DomainType = Literal['constant','cumulative','varying']

@dataclass
class Settings:
    positive_start_clauses: bool = True
    iterative_deepening: bool = False
    iterative_deepening_initial_depth: int = 1
    restricted_backtracking: bool = False
    backtrack_after: int = 2
    logic: LogicType = 'classical'
    domain: DomainType = 'constant'

class ConnectionEnv:
    def __init__(self, path: str, settings: Optional[Settings] = None):
        if settings is None:
            settings = Settings()

        self.path = path
        self.settings = settings
        self._parse_matrix(self.path)
        self._init_state()

    def _parse_matrix(self, path: str):
        if self.settings.logic == 'classical':
            from connections.utils.cnf_parsing import file2cnf
        else:
            from connections.utils.icnf_parsing import file2cnf
        self.matrix = file2cnf(path)

    def _init_state(self):
        logic_state_map = {
            'classical': 'connections.calculi.classical.ConnectionState',
            'intuitionistic': 'connections.calculi.intuitionistic.IConnectionState',
            'D': 'connections.calculi.modal_d.DConnectionState',
            'T': 'connections.calculi.modal_t.TConnectionState',
            'S4': 'connections.calculi.modal_s4.S4ConnectionState',
            'S5': 'connections.calculi.modal_s5.S5ConnectionState'
        }

        state_class_path = logic_state_map[self.settings.logic]
        module_name, class_name = state_class_path.rsplit('.', 1)
        module = __import__(module_name, fromlist=[class_name])
        state_class = getattr(module, class_name)

        self.state = state_class(self.matrix, self.settings)

    @property
    def action_space(self):
        if self.state.goal is None:
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
        self.state.reset()
        return self.state
