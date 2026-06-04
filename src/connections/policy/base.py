from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypeAlias

from connections.core.status import ProverOutcome
from connections.prover.actions import Action, ActionChoice
from connections.prover.state import State


PolicyOutput: TypeAlias = ActionChoice | ProverOutcome | None
BacktrackGranularity: TypeAlias = Literal["step", "maximal"]


class Policy(ABC):
    """Stateful search policy used by ``Prover``.

    Policies inspect the current state, query or maintain the current action
    set, and return one concrete action decision. The prover applies that action
    but does not choose among alternatives itself.
    """

    def __call__(self, state: State) -> PolicyOutput:
        actions = self.available_actions(state)
        if not actions:
            return self.no_action(state)
        action = self.next_action(state, actions)
        self._validate_action(action, actions)
        self.record_action_choice(state, action)
        return ActionChoice.from_action(actions, action)

    @abstractmethod
    def available_actions(self, state: State) -> tuple[Action, ...]:
        raise NotImplementedError

    @abstractmethod
    def next_action(self, state: State, actions: tuple[Action, ...]) -> Action:
        raise NotImplementedError

    def choose(
        self,
        actions: tuple[Action, ...],
        chosen_index: int,
    ) -> Action:
        if not 0 <= chosen_index < len(actions):
            raise RuntimeError(
                f"policy returned invalid index {chosen_index} "
                f"for {len(actions)} actions"
            )
        return actions[chosen_index]

    def no_action(self, state: State) -> ProverOutcome | None:
        return None

    def record_action_choice(self, state: State, action: Action) -> None:
        return None

    def record_proof_found(self, state: State) -> None:
        return None

    @staticmethod
    def _validate_action(
        action: Action,
        actions: tuple[Action, ...],
    ) -> None:
        if action not in actions:
            raise RuntimeError("policy returned an action outside available actions")


__all__ = [
    "BacktrackGranularity",
    "Policy",
    "PolicyOutput",
]
