# TODO

## Policy And Dynamics Boundary

- Simplify `IterativeDeepeningPolicy`. The `{i,m}leanCoP` trace-parity work
  pushed path-limit tracing and extension-candidate bookkeeping into policy in
  a way that blurs the policy/dynamics boundary. Keep current behavior for
  parity, but revisit the implementation so ID is again a small search-control
  layer over DFS and legal action generation stays in `Dynamics`.
