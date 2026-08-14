# Write a policy

A policy is an agent. It perceives the current state and returns an action:

```python
Policy = Callable[[State], Action | None]
```

That is the whole interface, and it is deliberately the agent-program shape:
percept in, action out. A policy returns *actions only*. Whether a state is
terminal, whether a budget has run out, and what any of it means are the
environment's to decide -- the rollout's, not the agent's.

Everything it wants to remember -- a stack of untried alternatives, a depth
bound, a search tree, a learned scorer -- is its own state, invisible to the
transition system. That is what makes a leanCoP-style search and a planner
instances of one interface rather than variants of the system.

## The smallest one

```python
from connections.policy import Policy

class FirstAdmissible(Policy):
    def __call__(self, state):
        actions = Dynamics.apply_actions(state)
        return actions[0] if actions else None
```

Returning `None` means "no action from me", and ends the rollout.

## Being told the search is over

A policy is called at **every** state it reaches, including a final one. There
is no separate notification hook, because being called *is* the notification.

That last call is where a policy settles whatever its memory holds -- choice
points that only become permanent on success, statistics to flush, a model to
detach -- after which it returns `None` and the rollout stops. Whatever it
returns at a final state is ignored: reaching an accepting state is the
environment's verdict, not something the agent can decline.

## Saying why you stopped

`None` is not self-explaining. A search that has exhausted its space says
something about the problem; a policy that merely has nothing to offer says
nothing at all. Only the policy knows which, so the rollout asks:

```python
    def stop_reason(self):
        return ProverOutcome.DFS_EXHAUSTED if self._exhausted else None
```

The default returns `None`, meaning no claim. This is a separate question from
the action channel on purpose -- an agent returns actions, not verdicts about
its environment, and the distinction is what keeps an exhausted search from
being confused with a budget running out.

You cannot make an unsound proof this way. A policy acts only through `T`, so
every state it reaches is a valid partial tableau and any accepting state is a
checkable closed tableau. Soundness is the system's; completeness is yours.

## Two axes, not six classes

Most of the family here factors into memory and choice:

| memory -- what `A(s, μ)` exposes | choice -- among what it exposed |
|---|---|
| none (markov) | first |
| depth-first stack | learned scorer |
| stack plus depth bound | |

leanCoP is stack-plus-bound with first-choice; the learned policies keep the
memory and replace the choice. Written as a hierarchy that becomes six classes
and a multiple-inheritance diamond; written as two axes it is three memories and
a chooser supplied by whoever has one.

```python
class Memory(Protocol):
    def exposed(self, state) -> Sequence[Action]:   # A(s, μ) ⊆ A(s)
    def update(self, state, action) -> None:        # U_π
    def stop_reason(self) -> ProverOutcome | None   # why nothing is left
    complete: bool                                  # does exhaustion mean anything

policy(memory, choose) -> Policy
```

`complete` is a soundness gate, not a label. Restricted backtracking sets it
false, and nothing downstream can then turn that policy's exhaustion into a
claim of `Satisfiable`.

## Shipped policies

```python
from connections.policy import DFSPolicy, IDPolicy, FirstActionIDPolicy
```

`DFSPolicy` keeps a stack of choicepoint frames. `IDPolicy` adds an iterative
deepening bound. `FirstActionIDPolicy` is leanCoP's discipline: first admissible
action, deepening on exhaustion.

The `cut` and `scut` settings are stack-pruning rules -- they discard frames or
alternatives more aggressively without changing `T`. Iterative deepening bounds
are a different controller memory, not a different transition system.

## Planners

A policy that runs thousands of transitions between being handed a state and
returning an action -- an rlCoP-style Monte-Carlo search -- fits neither slot
above. It needs the transition function and state copies of its own, so it
implements `__call__` directly and keeps its tree in its own memory.

The two-axis factoring is a convenience for reactive policies. `Policy` is the
only thing actually required.

## Copying state

The state is mutated in place, so several rollouts from one state need a copy
each. That is not too expensive: the matrix is immutable and shared, and only
the tableau and constraint store are duplicated.

## One thing to know about undo

The action space is not a stack. Any rule application the tableau carries may be
undone, not only the most recent, so a policy that wants stack discipline
imposes it in its own memory.

If you use that freedom, read the known gap in
[dynamics](../design/dynamics.md#undoing) first. Non-chronological undo can
currently leave a goal marked closed whose connection no longer holds. Shipped
depth-first policies do not trigger it because their undos happen to be
chronological; a policy with the full action space can.
