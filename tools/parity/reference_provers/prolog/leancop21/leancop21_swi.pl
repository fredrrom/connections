%% File: leancop21_swi.pl  -  Version: 2.1  -  Date: 30 Aug 2008
%% Connections changes:
%%  - added set_trace_mode/1 and trace_choice/1 for parity traces
%%  - traces start, extension, reduction, lemma, backtrack, regularity,
%%    path-limit, cut, and scut events
%%  - added set_step_limit/1 and step_tick/0 for inference-action budgets
%%  - added lit_trace/4 source metadata for source/rest trace rendering
%%  - blocked marker lemma reuse: # closes by reduction, not lemma(#,#)
%%  - suppressed marker-only #/-# reduction trace/counting and skips
%%    marker-only #/-# extension candidates in trace mode
%%
%%         "Make everything as simple as possible, but not simpler."
%%                                                 [Albert Einstein]
%%
%% Purpose: leanCoP: A Lean Connection Prover for Classical Logic
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de
%%
%% Usage: prove(M,P).    % where M is a set of clauses and P is
%%                       %  the returned connection proof
%%                       %  e.g. M=[[q(a)],[-p],[p,-q(X)]]
%%                       %  and  P=[[q(a)],[[-(q(a)),p],[[-(p)]]]]
%%        prove(F,P).    % where F is a first-order formula and
%%                       %  P is the returned connection proof
%%                       %  e.g. F=((p,all X:(p=>q(X)))=>all Y:q(Y))
%%                       %  and  P=[[q(a)],[[-(q(a)),p],[[-(p)]]]]
%%        prove2(F,S,P). % where F is a formula, S is a subset of
%%                       %  [nodef,def,conj,reo(I),scut,cut,comp(J)]
%%                       %  (with numbers I,J) defining attributes
%%                       %  and P is the returned connection proof
%%
%% Copyright: (c) 1999-2008 by Jens Otten
%% License:   GNU General Public License
:- [def_mm].  % load program for clausal form translation
:- dynamic(pathlim/0), dynamic(lit/4), dynamic(lit_trace/4), dynamic(trace_mode/1).
:- dynamic(step_limit/1), dynamic(step_count/1).

trace_mode(off).
step_limit(0).
step_count(0).

set_trace_mode(Mode) :-
    retractall(trace_mode(_)),
    assertz(trace_mode(Mode)).

trace_event(_) :-
    \+ trace_mode(on),
    !.
trace_event(Event) :-
    trace_event_name(Event, Name),
    write(Name), nl.

trace_event_name(start(_), start) :- !.
trace_event_name(start(_,_), start) :- !.
trace_event_name(extension(_,_), extension) :- !.
trace_event_name(extension(_,_,_,_), extension) :- !.
trace_event_name(reduction(_,_), reduction) :- !.
trace_event_name(lemma(_,_), lemma) :- !.
trace_event_name(factorization(_,_), factorization) :- !.
trace_event_name(backtrack(_), backtrack) :- !.
trace_event_name(pathlim(_), pathlim) :- !.
trace_event_name(pathlim_hit(_,_), pathlim_hit) :- !.
trace_event_name(regularity(_,_), regularity) :- !.
trace_event_name(cut(_), cut) :- !.
trace_event_name(scut(_), scut) :- !.
trace_event_name(Event, Event).

trace_choice(Event) :-
    trace_event(Event),
    ( trace_mode(on) -> ( true ; trace_event(backtrack(Event)), fail ) ; true ).

set_step_limit(Limit) :-
    retractall(step_limit(_)),
    assertz(step_limit(Limit)),
    retractall(step_count(_)),
    assertz(step_count(0)).

step_tick :-
    step_limit(Limit),
    ( Limit =< 0 -> true
    ; step_count(Count),
      Next is Count + 1,
      retractall(step_count(_)),
      assertz(step_count(Next)),
      ( Next > Limit -> throw(step_limit_reached) ; true )
    ).


%%% prove matrix M / formula F

prove(F,Proof) :- prove2(F,[cut,comp(7)],Proof).

prove2(F,Set,Proof) :-
    (F=[_|_] -> M=F ; make_matrix(F,M,Set)),
    retractall(lit(_,_,_,_)), (member([-(#)],M) -> S=conj ; S=pos),
    retractall(lit_trace(_,_,_,_)),
    assert_clauses(M,S), prove(1,Set,Proof).

prove(PathLim,Set,Proof) :-
    \+member(scut,Set) -> prove([-(#)],[],PathLim,[],Set,[Proof]) ;
    lit(#,_,C,_) -> trace_event(scut(start)), step_tick, trace_choice(start(C)), prove(C,[-(#)],PathLim,[],Set,Proof1),
    Proof=[C|Proof1].
prove(PathLim,Set,Proof) :-
    member(comp(Limit),Set), PathLim=Limit -> prove(1,[],Proof) ;
    (member(comp(_),Set);retract(pathlim)) ->
    PathLim1 is PathLim+1, trace_event(pathlim(PathLim1)), prove(PathLim1,Set,Proof).

%%% leanCoP core prover

prove([],_,_,_,_,[]).

prove([Lit|Cla],Path,PathLim,Lem,Set,Proof) :-
    Proof=[[[NegLit|Cla1]|Proof1]|Proof2],
    ( (member(LitC,[Lit|Cla]), member(LitP,Path), LitC==LitP) ->
      trace_event(regularity(LitC,LitP)), fail
    ; true ),
    (-NegLit=Lit;-Lit=NegLit) ->
       ( member(LitL,Lem), Lit==LitL, Lit \== #,
          step_tick,
          trace_choice(lemma(Lit,LitL)), Cla1=[], Proof1=[]
         ;
          member(NegL,Path), unify_with_occurs_check(NegL,NegLit),
          ( Lit == #, NegL == -(#) ->
            true
          ; step_tick,
            trace_choice(reduction(Lit,NegL))
          ),
          Cla1=[], Proof1=[]
         ;
          lit(NegLit,NegL,Cla1,Grnd1),
          unify_with_occurs_check(NegL,NegLit),
          trace_extension_candidate_allowed(Lit,NegL,Cla1),
          ( Grnd1=g -> true ; length(Path,K), K<PathLim -> true ;
            trace_event(pathlim_hit(PathLim,extension(Lit,NegL))), \+ pathlim -> assert(pathlim), fail ),
          ( Lit == #, NegL == -(#), Cla1 == [] ->
            true
          ; step_tick,
            trace_connection_choice(Lit,NegL,Cla1)
          ),
          prove(Cla1,[Lit|Path],PathLim,Lem,Set,Proof1)
        ),
       ( member(cut,Set) -> ( Lit == # -> true ; trace_event(cut(Lit)) ), ! ; true ),
       prove(Cla,Path,PathLim,[Lit|Lem],Set,Proof2).

trace_connection_choice(Lit,NegL,Cla1) :-
    trace_connection_source(NegL,Cla1,Source),
    trace_clause(Cla1,TraceCla1),
    ( Lit == -(#), NegL == # ->
      trace_choice(start(Cla1,Source))
    ; trace_choice(extension(Lit,NegL,Source,rest(TraceCla1)))
    ).

trace_connection_source(NegL,Cla1,source(ClauseId,LitIndex)) :-
    copy_term((NegL,Cla1),(NegLC,Cla1C)),
    once(lit_trace(NegLC,Cla1C,ClauseId,LitIndex)),
    !.
trace_connection_source(_,_,source(unknown,unknown)).

trace_clause([],[]).
trace_clause([Lit|Lits],[TraceLit|TraceLits]) :-
    trace_literal(Lit,TraceLit),
    trace_clause(Lits,TraceLits).

trace_literal(#,marker) :- !.
trace_literal(-(#),neg_marker) :- !.
trace_literal(Lit,Lit).

trace_extension_candidate_allowed(Lit,NegL,Cla1) :-
    trace_mode(on),
    Lit == #,
    NegL == -(#),
    Cla1 == [],
    !,
    fail.
trace_extension_candidate_allowed(_,_,_).

%%% write clauses into Prolog's database

assert_clauses(M,Set) :-
    assert_clauses(M,Set,0).

assert_clauses([],_,_).
assert_clauses([C|M],Set,ClauseId) :-
    (Set\=conj, \+member(-_,C) -> C1=[#|C] ; C1=C),
    (ground(C) -> G=g ; G=n), assert_clauses2(C1,[],G,ClauseId,0),
    ClauseId1 is ClauseId+1,
    assert_clauses(M,Set,ClauseId1).

assert_clauses2([],_,_,_,_).
assert_clauses2([L|C],C1,G,ClauseId,LitIndex) :-
    assert_renvar([L],[L2]), append(C1,C,C2), append(C1,[L],C3),
    assert(lit(L2,L,C2,G)), assert(lit_trace(L,C2,ClauseId,LitIndex)),
    LitIndex1 is LitIndex+1,
    assert_clauses2(C,C3,G,ClauseId,LitIndex1).

assert_renvar([],[]).
assert_renvar([F|FunL],[F1|FunL1]) :-
    ( var(F) -> true ; F=..[Fu|Arg], assert_renvar(Arg,Arg1),
      F1=..[Fu|Arg1] ), assert_renvar(FunL,FunL1).
