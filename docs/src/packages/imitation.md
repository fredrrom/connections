# imitation

Learned policies over `connections`: the model, the datasets built from found
proofs, the training loop, and the campaign machinery that runs all of it across
a corpus.

## The learning problem

Zero-shot multi-task. Proofs found on some problems supply demonstrations for
policies applied to problems never seen during training. Each problem is its own
transition system *P(M)*, so what transfers is parameters, not search state.

Given a closed tableau found by a behaviour policy *β*, replay it relative to a
target policy *π*. Replay reruns *π*'s memory update, giving the proof
trajectory

    τ^π = ((s₀, μ₀), a₀, (s₁, μ₁), ..., (sₙ, μₙ))

with `μ_{t+1} = U_π(μ_t, s_t, a_t)` and each `a_t ∈ A(s_t, μ_t)`. Training
raises the probability *π_θ* assigns each demonstrated action at its input --
behavioural cloning, a cross-entropy loss over the actions the calculus admits.

Replay can fail for a given target policy: if a demonstrated action is not in
`A(s_t, μ_t)` -- say the target's memory exposes only actions within a depth
bound the proof exceeded -- that proof yields no data for *that* policy, though
it may for another. The proof is a fact about *P(M)*; the trajectory is relative
to who is replaying it.

## Why this package is separate

`imitation` depends on `connections`, never the reverse. The library has no
notion of a model, a dataset, or a training round, and the seam that keeps it
that way is `Result`'s callback payload -- a trajectory is attached by a
callback the caller supplies, so `connections` never learns what training data
is.

It is also the one package that cannot parallelise by pickling its attempt: a
loaded model does not pickle. Its options are a CLI of its own to spawn, or
persistent workers that load once and read problems from a pipe, replaced when
one hangs. The second amortises a one-to-two second load that the first pays per
problem.

## Campaigns

    plan.py       what to run
    task.py       one unit of work
    claim.py      which worker owns which task
    worker.py     the process that executes them
    artifact.py   what comes back

A campaign is a training run's outer loop: prove a corpus with the current
policy, harvest the proofs, replay them into data, train, repeat. It has to
survive a killed job and resume, which is why claims and artifacts are explicit
rather than implied by a work queue.

This machinery is `imitation`'s, not the library's. If a second package ever
wants resumable corpus runs it becomes a distribution of its own -- and not
before.

## Relation to the dissertation

This package is the implementation behind the inter-conjecture chapter. The
notation here follows the paper: *β* for the behaviour policy, *π* for the
target, *τ^π* for a proof trajectory, *A(s, μ)* for what a policy's memory
exposes.
