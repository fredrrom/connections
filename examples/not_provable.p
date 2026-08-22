% The conjecture does not follow: q(b) is not forced by anything.
% A complete strategy exhausts and reports CounterSatisfiable; a pruned one
% reports GaveUp.
fof(p_implies_q, axiom, ![X] : (p(X) => q(X))).
fof(p_holds,     axiom, p(a)).
fof(goal,        conjecture, q(b)).
