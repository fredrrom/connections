from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple, Union

from connections.search.state import State

LogicType = Literal["classical", "intuitionistic", "D", "T", "S4", "S5"]
DomainType = Literal["constant", "cumulative", "varying"]


@dataclass(frozen=True)
class Settings:
    positive_start_clauses: bool = True
    iterative_deepening: bool = False
    iterative_deepening_initial_depth: int = 1
    restricted_backtracking: bool = False
    backtrack_after: int = 2
    logic: LogicType = "classical"
    domain: DomainType = "constant"


class ConnectionEnv:
    """Thin search environment around mutable calculus states."""

    def __init__(
        self, path: Union[str, Path], settings: Optional[Settings] = None
    ) -> None:
        self.path = str(path)
        self.settings = settings or Settings()
        self.matrix = self._parse_matrix(self.path)
        self.state = State(self.matrix, self.settings)

    def _parse_matrix(self, path: str) -> Any:
        if self.settings.logic == "classical":
            from connections.utils.cnf_parsing import file2cnf
        else:
            from connections.utils.icnf_parsing import file2cnf
        return file2cnf(path)

    @property
    def action_space(self) -> list[Any]:
        return self.state.action_space

    def step(self, action: Any) -> Tuple[Any, int, bool, Dict[str, str]]:
        if getattr(self.state, "is_terminal", False):
            return (
                self.state,
                int(self.state.is_terminal),
                self.state.is_terminal,
                {"status": str(self.state.info)},
            )
        self.state.update_goal(action)
        return (
            self.state,
            int(self.state.is_terminal),
            self.state.is_terminal,
            {"status": str(self.state.info)},
        )

    def reset(self) -> Any:
        self.matrix = self._parse_matrix(self.path)
        self.state = State(self.matrix, self.settings)
        return self.state
