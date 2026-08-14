%% SWI-Prolog compatibility layer for parity runs.
%%
%% This file is intentionally outside tools/parity/reference_provers/. It adapts the
%% SWI execution environment around the bundled leanCoP-family references
%% without changing those references.

:- if(current_prolog_flag(dialect, swi)).

:- op(1130, xfy, <=>).
:- op(1110, xfy, =>).
:- op(500, fy, #).
:- op(500, fy, *).
:- op(500, fy, ~).
:- op(500, fy, all).
:- op(500, fy, ex).
:- op(500, xfy, :).

:- multifile user:lib/1.
:- multifile '$toplevel':lib/1.

user:lib(_).
'$toplevel':lib(_).

:- multifile user:set_flag/2.
:- multifile '$toplevel':set_flag/2.

user:set_flag(occur_check,on) :- !,
    set_prolog_flag(occurs_check,true).
user:set_flag(Flag,Value) :-
    set_prolog_flag(Flag,Value).

'$toplevel':set_flag(occur_check,on) :- !,
    set_prolog_flag(occurs_check,true).
'$toplevel':set_flag(Flag,Value) :-
    set_prolog_flag(Flag,Value).

:- multifile user:retract_all/1.
:- multifile '$toplevel':retract_all/1.

user:retract_all(Head) :-
    retractall(Head).
'$toplevel':retract_all(Head) :-
    retractall(Head).

:- redefine_system_predicate(flatten/2).

flatten(Term,Flat) :-
    prefix_flatten(Term,Flat).

prefix_flatten(Term,[Term]) :-
    var(Term), !.
prefix_flatten([],[]) :- !.
prefix_flatten([Head|Tail],Flat) :- !,
    prefix_flatten(Head,HeadFlat),
    prefix_flatten(Tail,TailFlat),
    append(HeadFlat,TailFlat,Flat).
prefix_flatten(Term,Flat) :-
    nonvar(Term),
    Term=..[pre|Parts], !,
    prefix_flatten(Parts,PartFlat),
    Flat=[pre|PartFlat].
prefix_flatten(Term,[Term]).

compat_reference_matrix([],[]).
compat_reference_matrix([Clause|Clauses],[Normalized|NormalizedClauses]) :-
    compat_reference_clause(Clause,Normalized),
    compat_reference_matrix(Clauses,NormalizedClauses).

compat_reference_clause(FreeVars:Clause,FreeVars:NormalizedClause) :-
    is_list(Clause), !,
    compat_reference_literals(Clause,NormalizedClause).
compat_reference_clause(Clause,[]:NormalizedClause) :-
    compat_reference_literals(Clause,NormalizedClause).

compat_reference_literals([],[]).
compat_reference_literals([Literal|Literals],[Normalized|NormalizedLiterals]) :-
    compat_reference_literal(Literal,Normalized),
    compat_reference_literals(Literals,NormalizedLiterals).

compat_reference_literal((-Atom):(-Prefix),(-Atom):(-NormalizedPrefix)) :-
    compat_reference_prefix(Prefix,NormalizedPrefix), !.
compat_reference_literal((-Atom):Prefix,(-Atom):(-NormalizedPrefix)) :-
    compat_reference_prefix(Prefix,NormalizedPrefix), !.
compat_reference_literal(Atom:Prefix,Atom:NormalizedPrefix) :-
    compat_reference_prefix(Prefix,NormalizedPrefix), !.
compat_reference_literal(Literal,Literal).

compat_reference_prefix(Prefix,NormalizedPrefix) :-
    nonvar(Prefix),
    Prefix=..[pre|Parts], !,
    NormalizedPrefix=Parts.
compat_reference_prefix(Prefix,Prefix).

compat_tptp_axiom_path(Path) :-
    getenv('TPTP',Root), !,
    atom_concat(Root,'/',Path).
compat_tptp_axiom_path('').

compat_ileancop_main(File,Settings,Result) :-
    compat_tptp_axiom_path(AxiomPath),
    ( leancop_tptp2(File,AxiomPath,[_],Formula,Conjecture) ->
      Problem=Formula
    ; consult(File), f(Problem), Conjecture=non_empty ),
    ( Conjecture\=[] -> Problem1=Problem ; Problem1=(Problem=>false___) ),
    ( compat_ileancop_prove(Problem1,Settings) ->
      ( Conjecture\=[] -> Result='Theorem' ; Result='Unsatisfiable' )
    ; ( Conjecture\=[] -> Result='Non-Theorem' ; Result='Satisfiable' )
    ).

compat_ileancop_prove(Formula,Settings) :-
    make_matrix_intu(Formula,RawMatrix,Settings),
    compat_reference_matrix(RawMatrix,Matrix),
    retract_all(lit(_,_,_)),
    ( member([(-(#)):_],Matrix) -> Start=conj ; Start=pos ),
    assert_clauses(Matrix,Start),
    prove(1,Settings).

compat_mleancop_main(File,Settings,Result) :-
    ( nanocop_qmltp2(File,'',[_],Formula,Conjecture) ->
      ( Conjecture\=[] -> Problem=Formula ; Problem=(~Formula) ),
      rename_equal(Problem,Problem1),
      ( compat_mleancop_prove(Problem1,Settings,Proof) -> true ; true )
    ; consult(File), f(Problem), Conjecture=mleancop_format,
      rename_equal(Problem,Problem1),
      ( Problem1=[_|_] ->
        compat_reference_matrix(Problem1,Matrix),
        ( compat_mleancop_prove_matrix(Matrix,Settings,Proof) -> true ; true )
      ; ( compat_mleancop_prove(Problem1,Settings,Proof) -> true ; true )
      )
    ),
    ( nonvar(Proof) ->
      ( Conjecture\=[] -> Result='Theorem' ; Result='Unsatisfiable' )
    ; ( Conjecture\=[] -> Result='Non-Theorem' ; Result='Satisfiable' )
    ).

compat_mleancop_prove(Formula,Settings,Proof) :-
    make_matrix_modal(Formula,Settings,RawMatrix),
    compat_reference_matrix(RawMatrix,Matrix),
    compat_mleancop_prove_matrix(Matrix,Settings,Proof).

compat_mleancop_prove_matrix(Matrix,Settings,Proof) :-
    retractall(lit(_,_,_,_)),
    ( member([(-(#)):_],Matrix) -> Start=conj ; Start=pos ),
    assert_clauses(Matrix,Start),
    prove(1,Settings,Proof).

:- endif.
