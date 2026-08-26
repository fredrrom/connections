"""The actor-learner agent, and DAgger as its concrete instance.

An ``ActorLearnerAgent`` is an ordinary agent -- state in, action out --
whose internals are the actor-learner architecture of IMPALA, SEED and
Acme: per-episode actor replicas a driver requests and reports back on,
and a learner hook consulted only at the driver's wave tick. The parallel
face adds no semantics: it is the agent-supplied lifting of its own scalar
interface, legitimate because every replica acts under memory that is
frozen for the wave -- the driver ticks once per wave, after every episode
has returned, and theta moves nowhere else.

The agent keeps beliefs: a per-task record of definitive outcomes (closed,
exhausted), populated as episodes report back. Its halting rule covers
every mode with one statement: halt when a complete wave changed nothing
-- no new decided task and no model update -- since deterministic actors
under unchanged memory would replay the next wave verbatim.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from connections.agent import Agent, AgentOptions, AgentStatus, Chooser
from connections.environment.actions import Action
from connections.environment.state import State
from connections.interaction.records import Rollout

from imitation.critic import ObservationContext, ProofCloningCritic
from imitation.learning.trainer import SupervisedLearner
from imitation.performance import ActionModel, ModelChooser, PerformanceRecipe
from imitation.records import Example, dedupe
from imitation.tasks import EpisodeTask

logger = logging.getLogger(__name__)

DECIDED = frozenset(
    {
        AgentStatus.CLOSED,
        AgentStatus.DFS_EXHAUSTED,
        AgentStatus.ID_FIXED_POINT,
    }
)

Explore = Callable[[Chooser, EpisodeTask], Chooser]


def first_action(state: State, actions: Sequence[Action]) -> Action:
    """The symbolic base chooser: behavior before any theta exists."""

    _ = state
    return actions[0]


class ActorLearnerAgent(Agent):
    """An agent whose internals are a population of actors and a learner.

    Directly usable with a ``subagent_factory`` for evaluating any fixed
    policy; subclasses override ``subagent`` (the actor tier),
    ``observe_episode`` (an episode's outcome reported back) and
    ``improved`` (the learner tier, consulted once per wave, at the tick).
    """

    def __init__(
        self,
        subagent_factory: Callable[[EpisodeTask | None], Agent] | None = None,
        *,
        options: AgentOptions | None = None,
    ) -> None:
        super().__init__(options)
        self.task_status: dict[str, AgentStatus] = {}
        self._factory = subagent_factory
        self._wave_changed = False
        self._halted = False
        self._episodes: dict[int, tuple[State, Agent]] = {}

    # The scalar face: the theory. One conversation per state identity.

    def __call__(self, state: State) -> Action | None:
        entry = self._episodes.get(id(state))
        if entry is None or entry[0] is not state:
            entry = (state, self.subagent(None))
            self._episodes[id(state)] = entry
        action = entry[1](state)
        self.status = entry[1].status
        return action

    # The parallel face: the agent-supplied lifting of the same map.

    def observe_episode(self, task: EpisodeTask, attempt: Rollout) -> None:
        """Record what an episode decided about its task."""

        if attempt.status in DECIDED:
            key = str(task.problem.path)
            if self.task_status.get(key) != attempt.status:
                self.task_status[key] = attempt.status
                self._wave_changed = True

    def wave_completed(self) -> None:
        """The driver's structural tick: a full wave of episodes returned.

        The wave's shape is the experimenter's sampling plan, so only the
        driver knows where waves end; what happens on the tick is the
        agent's own. The learner is consulted here and nowhere else, which
        is the frozen-theta contract that makes replicas exchangeable.
        """

        improved = self.improved()
        self._halted = not (self._wave_changed or improved)
        self._wave_changed = False

    @property
    def halted(self) -> bool:
        return self._halted

    # The subclass surface.

    def subagent(self, task: EpisodeTask | None) -> Agent:
        if self._factory is None:
            raise NotImplementedError(
                "provide a subagent_factory or override subagent"
            )
        return self._factory(task)

    def improved(self) -> bool:
        return False


class _TapActor(Agent):
    """An episode replica: the recipe's agent with the critic listening.

    The tap is the only place the agent's side produces data, and it is
    inside the agent-environment loop: every percept, the closing state
    included, passes to the critic before the inner agent chooses.
    """

    def __init__(
        self, inner: Agent, critic: ProofCloningCritic, context: ObservationContext
    ):
        super().__init__(inner.options)
        self.inner = inner
        self.critic = critic
        self.context = context

    def __call__(self, state: State) -> Action | None:
        self.critic.observe(state, self.context)
        action = self.inner(state)
        self.status = self.inner.status
        return action


class DAggerAgent(ActorLearnerAgent):
    """Proof cloning iterated: collect proofs, retrain at the barrier.

    With ``learning`` off the same object is its own frozen evaluation
    version: the guard never fires and theta stays put. ``explore``, when
    set, may wrap an episode's chooser in an experimental one -- the
    problem generator's slot, degenerate by default.
    """

    def __init__(
        self,
        recipe: PerformanceRecipe,
        *,
        output_dir: str | Path,
        critic: ProofCloningCritic | None = None,
        learner: SupervisedLearner | None = None,
        explore: Explore | None = None,
        base_choose: Chooser = first_action,
        update_after: int = 1,
        learning: bool = True,
    ) -> None:
        super().__init__(options=recipe.options)
        self.recipe = recipe
        self.output_dir = Path(output_dir)
        self.critic = critic if critic is not None else ProofCloningCritic(recipe=recipe)
        self.learner = learner if learner is not None else SupervisedLearner()
        self.explore = explore
        self.base_choose = base_choose
        self.update_after = update_after
        self.learning = learning
        self.model: ActionModel | None = None
        self.round_index = 0
        self.checkpoints: list[Path] = []
        self._unique_at_update = 0

    def subagent(self, task: EpisodeTask | None) -> Agent:
        choose = self._chooser()
        if task is not None and self.explore is not None:
            choose = self.explore(choose, task)
        context = ObservationContext(
            problem_path="" if task is None else str(task.problem.path),
            round_index=self.round_index,
            behavior_name="base" if self.model is None else f"pi_{self.round_index}",
        )
        return _TapActor(
            inner=self.recipe.with_chooser(choose),
            critic=self.critic,
            context=context,
        )

    def improved(self) -> bool:
        """The learner tier: retrain when a wave brought new choicepoints."""

        if not self.learning:
            return False
        feedback = self.critic.feedback()
        unique = len(dedupe(feedback))
        new = unique - self._unique_at_update
        if new < self.update_after:
            logger.info(
                "barrier declined: %d new choicepoints (< %d), theta unchanged",
                new,
                self.update_after,
            )
            return False
        logger.info(
            "barrier: %d examples, %d unique choicepoints (%d new), training round %d",
            len(feedback),
            unique,
            new,
            self.round_index,
        )
        checkpoint = self.output_dir / f"round_{self.round_index:03d}"
        self.model = self.learner.improve(feedback, output_dir=checkpoint)
        self.checkpoints.append(checkpoint)
        self._unique_at_update = unique
        self.round_index += 1
        return True

    def performance_copy(self) -> Agent:
        """A fresh performance element under the current frozen theta."""

        return self.recipe.with_chooser(self._chooser())

    def experience(self) -> tuple[Example, ...]:
        return self.critic.feedback()

    def _chooser(self) -> Chooser:
        if self.model is None:
            return self.base_choose
        return ModelChooser(preprocess=self.recipe.preprocess, model=self.model)


__all__ = [
    "ActorLearnerAgent",
    "DAggerAgent",
    "DECIDED",
    "Explore",
    "first_action",
]
