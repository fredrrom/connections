# Prove a problem

Two ways in: the `pycop` command line, or `run` from Python. They do the same
thing -- the CLI is argument parsing, SZS on stdout, and an exit code around one
call.

## From the command line

```bash
uv run pycop path/to/problem.p
```

Point it at a directory instead and it walks the tree for problem files.

Common flags:

| | |
|---|---|
| `--settings` | a leanCoP-style setting, repeatable: `def`, `nodef`, `conj`, `cut`, `scut`, `comp(7)` |
| `--schedule` | a named strategy schedule instead of single settings |
| `--steps` | transition-step budget |
| `--timeout` | wall-clock budget in seconds |
| `--logic` / `--domain` | classical, intuitionistic, or modal, with a domain condition |
| `--source-dir` | where to resolve `include` directives from |
| `--metrics` | machine-readable run metrics for a single problem |
| `--trace-search` | print proof-search trace events |
| `--trace-clausification` | print clausification and matrix-construction events |

A step budget is the portable one. The same `--timeout` is a different budget on
different hardware, which is why reported effort should be steps -- see
[running](../design/running.md).

## From Python

```python
from connections.run import build_state, rollout, run

result = run(problem_spec, schedule=schedule)
print(result.szs_status)
```

`run` handles one problem, in the calling process. It builds a state per
strategy in the schedule, instantiates that strategy's policy, rolls out under
its share of the budget, and stops at the first success.

To work below that -- a single rollout in a system you already have:

```python
state = build_state(problem_spec, matrix_options=matrix_options)
rollout_result = rollout(state, policy=policy, step_limit=10_000)
```

`rollout` takes no problem and no schedule. By the time it starts, *P(M)* exists
and the state is a point in it.

## Reading the result

```python
result.szs_status        # Theorem, Unsatisfiable, ResourceOut, ...
result.outcome           # why the run stopped
result.strategy_results  # one per strategy in the schedule
result.to_dict()         # JSON-able; the entire data contract
```

`Theorem` and `Unsatisfiable` differ by whether the problem had a conjecture, a
distinction settled during clausification rather than guessed at afterwards.
`Satisfiable` and `CounterSatisfiable` are reported only from a *complete*
strategy: a policy with restricted backtracking has pruned its space, so
exhausting what remains says nothing about the whole.

`Timeout` and `MemoryOut` are never reported by a run. They are claims about a
process and belong to whatever supervised it.

## Many problems

`connections` does not do this, on purpose. A run is one problem, and running
many is many runs -- arranging them is the caller's, because a laptop, a
400-core queue, and a mixed-hardware fleet want different answers.

The practical shape is a subprocess per problem, since `subprocess.run(timeout=)`
kills and reaps a child that will not stop and OOM arrives as a signal in the
return code. See [running](../design/running.md#running-many-problems).
