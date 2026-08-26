# imitation

A learning agent over `connections`, in Russell and Norvig's sense: one part
of the system makes choices, and the others generate and judge them. The
package is the four components of their learning-agent diagram, each a
module you can point at, wired by an `ActorLearnerAgent` that is itself an
ordinary `Agent` -- percept in, action out -- with the learning machinery
entirely behind that interface. Its parallel face adds no semantics: it is
the agent-supplied lifting of its own scalar interface, legitimate because
replicas act under memory frozen for the wave.

## The components

| R&N component | Here | Module |
|---|---|---|
| Performance element | a `connections` agent whose chooser is learned | `performance` |
| Performance standard | proofhood, decided by the calculus, outside the agent | `connections.interaction` |
| Critic | proof states replayed into labeled demonstrations | `critic` |
| Learning element | the graph network fitted to the demonstrations | `representation`, `model`, `learning` |
| Problem generator | the `explore` chooser transform; degenerate in proof cloning | `actor_learner` |

The environment is the corpus of tasks: conceptually one contextual
transition system whose state already carries its matrix, so the percept is
[s, &omega;] by construction and needs no augmentation. The task embedding
is the model's matrix tier -- computed from &omega; itself,
signature-invariant, so conditioning generalizes to unseen tasks instead of
memorizing identifiers. Which task to attempt next is the environment's
draw, not the agent's choice: `run` receives the corpus -- the vector of
initial states -- from outside and cycles it, one episode per problem per
pass.

The performance element is a live agent built by a `PerformanceRecipe` --
agent class, options, preprocessor -- and the recipe is the single source
of truth for the action surface. An example's label space is exactly the
candidate sequence the chooser was shown, in order; replay and inference
agree because both build their agents from the same recipe, and a dataset
refuses to mix `surface_key`s. Search agents are stateful, so every episode
gets a fresh performance element built from the frozen round model;
`AllActionsMarkovAgent` widens the surface to the whole of A(s), undos
included, for the memoryless policy that can learn to backtrack.

The critic judges observed states against the standard, and it receives
them through the front door: the rollout contract calls the agent at every
state it reaches, the closing one included, so every actor the agent
lends taps the critic with each percept and no callback machinery exists. A state
that is a proof is stored and replayed -- the same agent class under a
perfectly informed chooser that picks, at each choicepoint, the shown
candidate matching an unused goal of the closed proof. Forced moves carry
no decision and produce no example. A proof the surface cannot reconstruct
is a recorded `ReplayFailure`, never a repair.

The learning element is the barrier, and the agent owns its trigger: at
the driver's wave tick it improves exactly when new choicepoints have
accumulated, so a pass that only re-finds known proofs leaves theta alone
-- which is also the halting rule, stated once for every mode: halt when a
complete pass changed nothing, neither a belief nor the model. Theta is
piecewise-constant -- the tick refuses to fire with actors on loan, so
within a wave every replica acts under the same frozen model and a
parallel run provably equals a serial one; see the rounds protocol in
[running](../design/running.md).

## The actor-learner agent and the experiment loop

`ActorLearnerAgent` is an ordinary agent whose internals are the
actor-learner architecture of IMPALA, SEED and Acme: a fixed pool of
per-episode actor replicas a driver borrows (`checkout`) and returns
(`checkin`), per-task beliefs recording definitive outcomes, and a learner
hook consulted at the wave tick. `DAggerAgent` is its concrete instance,
and its `learning` switch off makes the same object its own frozen
evaluation version. Ours is the synchronous variant of the architecture --
no off-policy correction is needed because replay labeling stays on-policy
per round.

`run_experiment(agent, problems, horizon=H, total_steps=N)` in
`experiment` is the driver, and the loop is the experimenter's sampling
plan: which problems, how many episodes per problem per pass, what budgets
(`total_steps` is a stopping criterion checked at pass boundaries, like
RLlib's total-timesteps). It builds records from the library's step
accounting -- with the proof attached, in replayable form, when one is
found -- so its report is prover output, and parallelism is an injected
`concurrent.futures` executor bounded by the agent's pool. Evaluation is
`evaluate(build, problems, horizon=H)`: the same loop under a frozen
actor factory.

## Measures

Evaluation happens above the agent. `experiment` computes, from the records
that `interaction` already produces: success J_S, search cost J_T, proof
size J_L, directness J_D, and the waste W = T - |s_T| of an attempt --
zero exactly when the search never backtracks. `success_curve` recovers
J_S at every budget below the one the runs used, because success is
monotone in the budget; asking beyond it is an error, not an extrapolation.

## Training loop

```python
from connections.agent import OnlineIDAgent
from imitation import DAggerAgent, PerformanceRecipe, run_experiment

agent = DAggerAgent(
    PerformanceRecipe(agent_class=OnlineIDAgent), output_dir=out
)
report = run_experiment(agent, problems, horizon=100, total_steps=1_000_000)
```

The first pass acts with the symbolic first-action chooser; every later
pass acts with the model the previous barrier produced -- the DAgger loop,
with the difference that the expert cannot be queried: a proof labels only
its own path, so the training distribution follows the policy only through
its successes.
