# imitation

Code for [*Imitation Learning for Connection-Tableau Construction*](https://arxiv.org/abs/2608.26009)
(Rømming et al., 2026).

## Reproducing the experiments

The corpora of the paper are fetched by the library's downloader, and one
command runs the training loop on each:

```bash
uv sync --all-packages
uv run connections-download-corpora m2k mptp2078 tptp-v9.2.1
```

Train on a corpus (M2k shown; substitute the other corpus directories for
MPTP2078 and TPTP):

```bash
uv run imitation-experiment corpora/m2k \
    --surface id --horizon 100 --total-steps 5000000 \
    --lr-schedule cosine --workers 8 --output artifacts/m2k-id
```

`--surface` picks the search agent the learned chooser acts through --
`id`, `dfs`, or the whole-surface `all-actions` policy that can learn to
backtrack (the paper's $\pi_{\mathrm{id}}$, $\pi_{\mathrm{dfs}}$,
$\pi_{\mathrm{markov}}$). The command prints, per training pass, the
measures below, plus coverage and retention across passes. Checkpoints and
the collected demonstration examples land under `--output`.

## The measures

An episode on a problem $\omega$ is a trajectory
$\tau = (s_0, a_0, s_1, \ldots, s_T)$ from the empty derivation
$s_0 = \varepsilon$. Write $s_t : \omega$ when the derivation $s_t$ is a
closed tableau for $\omega$; that, or the horizon $H$, is what stops it:

```math
T = \min\bigl(H,\ \inf\{t \mid s_t : \omega\}\bigr).
```

Each step appends at most one inference to the derivation, so
$|s_T| \le T$. The printed columns are empirical averages over a pass's
episodes -- a checkmark subscript averages over the successful episodes
only:

```math
\hat{J}_S = \mathrm{avg}\ \mathbf{1}\{s_T : \omega\}, \qquad
\hat{J}_T = \mathrm{avg}_{\checkmark} T, \qquad
\hat{J}_L = \mathrm{avg}_{\checkmark} |s_T|, \qquad
\hat{J}_D = \mathrm{avg}_{\checkmark} \tfrac{|s_T|}{T},
```

the success rate, the search cost, the proof size, and the directness of
the search: estimates of the corresponding expectations under the policy
over the task distribution.
Directness is the fraction of steps that survived into the proof --
equivalently one minus the normalized waste $W(\tau) = T - |s_T|$, the
exact regret against an oracle that knew in advance which derivation it
was building. $W = 0$ exactly when the search never backtracks, so a
perfectly imitated proof scores $J_D = 1$ however large the proof is.
Retention between passes compares solved sets under consecutive policies:
proofs kept, gained, and forfeited by an update.

The full corpora are compute-heavy; for a smoke run, limit the task count:

```bash
uv run imitation-experiment corpora/m2k --limit 20 --horizon 100 \
    --total-steps 100000 --output artifacts/m2k-smoke
```
