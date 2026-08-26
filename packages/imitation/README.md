# imitation

Code for *Imitation Learning for Connection-Tableau Construction*
(Rømming et al., 2026).
<!-- add arXiv link once announced -->

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
backtrack (the paper's pi_id, pi_dfs, pi_markov). The command prints, per
training pass, the measures: problems solved and success rate J_S, search
cost J_T, proof size J_L, and directness J_D, plus coverage and retention
across passes. Checkpoints and the collected demonstration examples land
under `--output`.

The full corpora are compute-heavy; for a smoke run, limit the task count:

```bash
uv run imitation-experiment corpora/m2k --limit 20 --horizon 100 \
    --total-steps 100000 --output artifacts/m2k-smoke
```
