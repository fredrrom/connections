# Write an agent

An agent perceives the current state and returns an action:

```python
class Agent:
    def __init__(self, options: AgentOptions | None = None): ...
    def __call__(self, state) -> Action | None: ...
    status: AgentStatus     # a plain attribute
```

Percept in, action out. An agent returns *actions only*: whether a budget has
run out and what any of it means for the problem are the prover's to decide.
Returning `None` ends the rollout.

## The smallest one

```python
from connections.agent import Agent
from connections.calculus.dynamics import Dynamics


class FirstAdmissible(Agent):
    def __call__(self, state):
        for goal in state.fringe:
            actions = Dynamics.apply_actions(
                state, goal, start="positive"
            ).ordered()
            if actions:
                return actions[0]
        return None
```

Start selection is yours, like factorization: the matrix's role indexes are
facts, and which subset you query is your option.

You cannot make an unsound proof this way. An agent acts only through `T`, so
every state it reaches is a valid partial tableau, and the judge verifies any
claimed closure against the state itself. Soundness is the system's;
completeness is yours.

## Observing the end

You are called at every state you reach, including a final one: closure
arrives through the percept (`state.tableau.root.closed`), and that last call
is where you settle whatever your memory holds before returning `None`. The
rollout never reads the tableau; what you make of the state is your business,
and what your result means is the judge's.

## Saying why you stopped

`None` is not self-explaining, so the rollout reads `self.status` once:

```python
from connections.agent import AgentStatus

    self.status = AgentStatus.GAVE_UP     # the default: no claim
```

`CLOSED` says you observed your derivation close. `DFS_EXHAUSTED` and
`ID_FIXED_POINT` affirmatively claim systematic coverage of a complete
fragment of the action space -- claim them only if your search ignored
nothing but redundant rule families. Cut, scut, conjecture start, or a depth
bound that ever bound all forfeit the claim; answer `GAVE_UP`, which is always
honest. The judge maps claims to `CounterSatisfiable`/`Satisfiable` and
`GAVE_UP` to SZS `GaveUp`, and never asks you about the problem.

## Compose, don't subclass

Most reactive agents are a memory and a chooser:

```python
from connections.agent import AgentOptions, OnlineDFSAgent, OnlineIDAgent

deepening = OnlineIDAgent(my_scorer, AgentOptions(comp=7))
learned = OnlineDFSAgent(my_scorer, AgentOptions(factorization="equal"))
```

The memory is the search: it exposes `A(s, μ)`, updates on the chosen
action, and sets `self.status` as it learns. The chooser picks among what
is exposed and nothing else -- `first` reproduces leanCoP order; a learned
scorer is just another chooser. A planner that runs transitions of its own
between percept and action fits neither slot and implements `Agent` directly.

## Memory across episodes

By default `run` builds a fresh agent per schedule entry, so memory dies with
the rollout. Pass `run(..., agent=your_agent)` to persist one agent across
entries -- then which strata of your memory survive which boundary is yours to
manage, keyed off the percept: the context ω is in every state, so detecting
a new attempt, a new ω, or a new problem needs no side channel. Ordering
memory (statistics) carries safely; pruning memory forfeits your exhaustion
claim for that episode.

## Copying state

The state is mutated in place, so several rollouts from one state need a copy
each. That is not too expensive: the matrix is immutable and shared, and only
the tableau and constraint store are duplicated.

## One thing to know about undo

The action space is not a stack. Any rule application the tableau carries may
be undone, not only the most recent; a search that wants stack behaviour
imposes it in its own memory. If you use the full freedom, read the known gap
in [dynamics](../design/dynamics.md#undoing) first: non-chronological undo can
currently leave a goal marked closed whose connection no longer holds.
