% A chained modus ponens with a distractor axiom: the prover has to pick the
% right extensions and backtrack past r/1, which never helps.
% SZS status: Theorem
fof(p_implies_q, axiom, ![X] : (p(X) => q(X))).
fof(q_implies_s, axiom, ![X] : (q(X) => s(X))).
fof(distractor,  axiom, ![X] : (r(X) => s(X))).
fof(p_holds,     axiom, p(a)).
fof(goal,        conjecture, s(a)).
