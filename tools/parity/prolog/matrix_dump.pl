%% Matrix dump helper for parity diagnostics.
%%
%% This file is intentionally outside tools/parity/reference_provers/. It only prints
%% already-translated matrices in a stable format for Python-side comparison.

dump_matrix(Matrix) :-
    numbervars(Matrix,0,_),
    write('MATRIX '),
    write_canonical(Matrix),
    nl,
    forall(member(Clause,Matrix),(
        write('CLAUSE '),
        write_canonical(Clause),
        nl
    )).

matrix_negated(Formula,Negated) :-
    Negated =.. ['~',Formula].

matrix_implies(Left,Right,Implication) :-
    Implication =.. ['=>',Left,Right].
