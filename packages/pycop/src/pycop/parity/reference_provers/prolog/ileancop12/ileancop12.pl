%% File: ileancop12.pl  -  Version: 1.2  -  Date: 07 June 2007
%% Connections changes:
%%  - merged def_mm_intu_f behavior into def_mm_intu.pl
%%  - added set_trace_mode/1 and trace_choice/1 for parity traces
%%  - traces start, extension, reduction, lemma, backtrack, regularity,
%%    path-limit, cut, and scut events
%%  - added set_step_limit/1 and step_tick/0 for inference-action budgets
%%  - blocked marker lemma reuse: # closes by reduction, not lemma(#,#)
%%  - suppressed marker-only #/-# reduction trace/counting and skips
%%    marker-only #/-# extension candidates in trace mode
%%
%%         "Make everything as simple as possible, but not simpler."
%%                                                 [Albert Einstein]
%%
%% Purpose: ileanCoP: A Connection Prover for Intuitionistic Logic
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/ileancop/
%%
%% Usage:   prove(F).    % where F is a first-order formula
%%                       %  e.g. F=((p,all X:(p=>q(X)))=>all Y:q(Y))
%%          prove2(F,S). % where F is a formula and S is a subset of
%%                       %  [nodef,def,conj,reo(I),scut,cut,comp(J)]
%%                       %  (with numbers I,J) defining attributes
%%
%% Copyright: (c) 2005-2007 by Jens Otten
%% License:   GNU General Public License


:- [def_mm_intu].  % load program for clausal form translation
:- lib(iso).       % load library for ISO compatibility
:- set_flag(occur_check,on).  % global occur check on
:- dynamic(pathlim/0), dynamic(lit/3), dynamic(trace_mode/1).
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
      ( Next >= Limit -> throw(step_limit_reached) ; true )
    ).


%%% prove formula F

prove(F) :- prove2(F,[def,scut,cut,comp(7)]).

prove2(F,Set) :-
    Time1 is cputime, make_matrix_intu(F,M,Set),
    retract_all(lit(_,_,_)), (member([(-(#)):_],M) -> S=conj ; S=pos),
    assert_clauses(M,S), prove(1,Set),
    Time2 is cputime, Time is Time2-Time1, print(Time).

prove(PathLim,Set) :-
    ( \+member(scut,Set) ->
      step_tick,
      prove([(-(#)):(-[])],[],PathLim,[],[PreSet,FreeV1],Set) ;
      lit((#):_,FV:C,_) ->
      trace_event(scut(start)), step_tick, trace_choice(start(C)),
      prove(C,[(-(#)):(-[])],PathLim,[],[PreSet,FreeV],Set),
      append(FreeV,FV,FreeV1) ),
      check_addco(FreeV1), prefix_unify(PreSet).
prove(PathLim,Set) :-
    member(comp(Limit),Set), PathLim=Limit -> prove(1,[]) ;
    (member(comp(_),Set);retract(pathlim)) ->
    PathLim1 is PathLim+1, trace_event(pathlim(PathLim1)), prove(PathLim1,Set).

%%% ileanCoP core prover

prove([],_,_,_,[[],[]],_).

prove([Lit:Pre|Cla],Path,PathLim,Lem,[PreSet,FreeV],Set) :-
    ( (member(LitC,[Lit:Pre|Cla]), member(LitP,Path), LitC==LitP) ->
      trace_event(regularity(LitC,LitP)), fail
    ; true ),
    (-NegLit=Lit;-Lit=NegLit) ->
       ( member(LitL,Lem), Lit:Pre==LitL, Lit \== #, step_tick, trace_choice(lemma(Lit:Pre,LitL)), PreSet3=[], FreeV3=[]
         ;
          member(NegL:PreN,Path), unify_with_occurs_check(NegL,NegLit),
          ( Lit == #, NegL == -(#) ->
            true
          ; step_tick,
            trace_choice(reduction(Lit:Pre,NegL:PreN))
          ),
          \+ \+ prefix_unify([Pre=PreN]), PreSet3=[Pre=PreN], FreeV3=[]
         ;
          lit(NegLit:PreN,FV:Cla1,Grnd1),
          \+ \+ prefix_unify([Pre=PreN]),
          trace_extension_candidate_allowed(Lit,NegLit,Cla1),
          ( Grnd1=g -> true ; length(Path,K), K<PathLim -> true ;
            trace_event(pathlim_hit(PathLim,extension(Lit:Pre,NegLit:PreN))), \+ pathlim -> assert(pathlim), fail ),
          ( Lit == #, NegLit == -(#), Cla1 == [] ->
            true
          ; step_tick,
            ( Lit == -(#), NegLit == # -> trace_choice(start(Cla1)) ;
              trace_choice(extension(Lit:Pre,NegLit:PreN)) )
          ),
          prove(Cla1,[Lit:Pre|Path],PathLim,Lem,[PreSet1,FreeV1],Set),
          PreSet3=[Pre=PreN|PreSet1], append(FreeV1,FV,FreeV3)
       ),
       ( member(cut,Set) -> ( Lit == # -> true ; trace_event(cut(Lit:Pre)) ), ! ; true ),
       prove(Cla,Path,PathLim,[Lit:Pre|Lem],[PreSet2,FreeV2],Set),
       append(PreSet3,PreSet2,PreSet), append(FreeV2,FreeV3,FreeV).

trace_extension_candidate_allowed(Lit,NegLit,Cla1) :-
    trace_mode(on),
    Lit == #,
    NegLit == -(#),
    Cla1 == [],
    !,
    fail.
trace_extension_candidate_allowed(_,_,_).

%%% write clauses into Prolog's database

assert_clauses([],_).
assert_clauses([FV:C|M],Set) :-
    (Set\=conj, \+member((-_):_,C) -> C1=[(#):[]|C] ; C1=C),
    (ground(C) -> G=g ; G=n), assert_clauses2(C1,[],G,FV),
    assert_clauses(M,Set).

assert_clauses2([],_,_,_).
assert_clauses2([L|C],C1,G,FV) :-
    append(C1,C,C2), assert(lit(L,FV:C2,G)), append(C1,[L],C3),
    assert_clauses2(C,C3,G,FV).


%%% prefix unification

prefix_unify([]).
prefix_unify([S=T|G]) :- (-S2=S -> T2=T ; -S2=T, T2=S),
                         flatten([S2,_],S1), flatten(T2,T1),
                         tunify(S1,[],T1), prefix_unify(G).

tunify([],[],[]).
tunify([],[],[X|T])       :- tunify([X|T],[],[]).
tunify([X1|S],[],[X2|T])  :- (var(X1) -> (var(X2), X1==X2);
                             (\+var(X2), unify_with_occurs_check(X1,X2))),
                             !, tunify(S,[],T).
tunify([C|S],[],[V|T])    :- \+var(C), !, var(V), tunify([V|T],[],[C|S]).
tunify([V|S],Z,[])        :- unify_with_occurs_check(V,Z), tunify(S,[],[]).
tunify([V|S],[],[C1|T])   :- \+var(C1), V=[], tunify(S,[],[C1|T]).
tunify([V|S],Z,[C1,C2|T]) :- \+var(C1), \+var(C2), append(Z,[C1],V1),
                             unify_with_occurs_check(V,V1),
                             tunify(S,[],[C2|T]).
tunify([V,X|S],[],[V1|T])     :- var(V1), tunify([V1|T],[V],[X|S]).
tunify([V,X|S],[Z1|Z],[V1|T]) :- var(V1), append([Z1|Z],[Vnew],V2),
                                 unify_with_occurs_check(V,V2),
                                 tunify([V1|T],[Vnew],[X|S]).
tunify([V|S],Z,[X|T])     :- (S=[]; T\=[]; \+var(X)) ->
                             append(Z,[X],Z1), tunify([V|S],Z1,T).

%%% check additional quantifier/prefix interaction condition

check_addco([]).
check_addco([[X,Pre]|L]) :- addco(X,Pre), check_addco(L).

addco(X,_)          :- (atomic(X);var(X);X==[[]]), !.
addco(_^_^Pre1,Pre) :- !, prefix_unify([-Pre1=Pre]).
addco(T,Pre)        :- T=..[_,T1|T2], addco(T1,Pre), addco(T2,Pre).
