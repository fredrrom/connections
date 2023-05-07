%% Version: 1.0  -  Date: 25/11/2004  -  File: ileancop.pl
%%          1.0f -  Date: 12/12/2022  -  File: mleancop10f.pl
%%            - no re-shuffling of clauses in Mat
%%            - ground clauses are not removed from Mat
%%            - start clause not moved to beginning of Mat
%%            - path limit check also for propositional clauses
%%            - iterative deeping is always done
%%            - added extended regularity (check whole clause)
%%
%% Purpose: MleanCoP: A Connection Prover for Modal Logic
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/mleancop/
%%
%% Usage:   prove(F).   % where F is a modal first-order formula,
%%                      %  e.g. F=((# all X:p(X)) => all X: * p(X))
%%
%% Copyright: (c) 2005-2023 by Jens Otten
%% License:   GNU General Public License

logic(s4).  % specify modal logic (d,t,s4,s5)
domain(cumul).  % specify domain condition (const,cumul,vary)

:- lib(iso).  % load library for ISO compatibility
:- set_flag(occur_check,on).  % global occurs check on
:- [mleancop_defmm]. % module for translation into prefixed matrix

:- dynamic(count/1).
%:- dynamic(pathlim/0).

% -----------------------------------------------------------------
% prove(F) - prove formula F

prove(F) :- prove2(F,[]).

prove2(F,Set) :- retract_all(count(_)), assert(count(0)),
                 Time1 is cputime, make_matrix_modal(F,Set,M), prove(M,1),
%                 retract(count(I)),print(successful_connections:I),nl,
                 Time2 is cputime, Time is Time2-Time1, print(Time).

prove(Mat,PathLim) :-
     append(MatA,[FV:Cla|MatB],Mat), \+member(-(_):_,Cla),
     append(MatA,[FV:[-(!):(-[])|Cla]|MatB],Mat1),
     prove([!:[]],[!:[]],Mat1,[],PathLim,[PreSet,FreeV]),
     domain_cond(FreeV), prefix_unify(PreSet).

prove(Mat,PathLim) :-
     PathLim1 is PathLim+1, prove(Mat,PathLim1).

prove([],_,_,_,_,[[],[]]).

prove([Lit:Pre|Cla],Cla4,Mat,Path,PathLim,[PreSet,FreeV]) :-
     \+ (member(LitC,Cla4), member(LitP,Path), LitC==LitP),
     (-NegLit=Lit;-Lit=NegLit) ->
        ( member(NegL:PreN,Path), unify_with_occurs_check(NegL,NegLit),
          \+ \+ prefix_unify([Pre=PreN]), PreSet1=[], FreeV3=[],
%%          print(reduction(Lit:Pre,NegL:PreN)), nl,
          retract(count(I)), I1 is I+1, assert(count(I1))
          ;
          member(Cla1,Mat), copy_term(Cla1,FV:Cla2),
          length(Path,K), K<PathLim,
          append(ClaA,[NegL:PreN|ClaB],Cla2),
          unify_with_occurs_check(NegL,NegLit),
          \+ \+ prefix_unify([Pre=PreN]),
%%          print(extension(Lit:Pre,NegL:PreN)), nl,
          retract(count(I)), I1 is I+1, assert(count(I1)),
          append(ClaA,ClaB,Cla3),
          prove(Cla3,Cla3,Mat,[Lit:Pre|Path],PathLim,[PreSet1,FreeV1]),
          append(FreeV1,FV,FreeV3)
        ),
        prove(Cla,Cla4,Mat,Path,PathLim,[PreSet2,FreeV2]),
        append([Pre=PreN|PreSet1],PreSet2,PreSet),
        append(FreeV2,FreeV3,FreeV).

% -----------------------------------------------------------------
% prefix_unify(PrefixEquations) - prefix unification

prefix_unify([]).
prefix_unify([S=T|G]) :-
    ( -S2=S -> T2=T ; -S2=T, T2=S ),
    ( logic(s5) -> S1=S2, T1=T2 ;  flatten(S2,S1), flatten(T2,T1) ),
    ( logic(s5) -> tuni_s5(S1,T1) ;
      logic(d)  -> tuni_d(S1,T1) ;
      logic(t)  -> tuni_t(S1,[],T1) ;
      logic(s4) -> tunify(S1,[],T1) ),
    prefix_unify(G).

% rules for D
tuni_d([],[]).
tuni_d([X1|S],[X2|T]) :- unify_with_occurs_check(X1,X2), tuni_d(S,T).

% rules for T
tuni_t([],[],[]).
tuni_t([],[],[X|T])      :- tuni_t([X|T],[],[]).
tuni_t([V|S],[],[])      :- V=[], tuni_t(S,[],[]).
tuni_t([X1|S],[],[X2|T]) :- (var(X1) -> (var(X2), X1==X2);
                            (\+var(X2), unify_with_occurs_check(X1,X2))),
                            !, tuni_t(S,[],T).
tuni_t([V|S],[],[X|T])   :- var(V), tuni_t([V|S],[X],T).
tuni_t([C|S],[],[V|T])   :- \+var(C), var(V), tuni_t([V|T],[C],S).
tuni_t([V1|S],[],[V2|T]) :- var(V1), V2=[], tuni_t(T,[V1],S).
tuni_t([V|S],[X],T)      :- V=[], tuni_t(S,[X],T).
tuni_t([V|S],[X],T)      :- var(V), unify_with_occurs_check(V,X),
                            tuni_t(S,[],T).
tuni_t([C|S],[V],T)      :- \+var(C), var(V), unify_with_occurs_check(V,C),
                            tuni_t(S,[],T).

% rules for S4
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
tunify([V,X|S],[],[V1|T]) :- var(V1), tunify([V1|T],[V],[X|S]).
tunify([V,X|S],[Z1|Z],[V1|T]) :- var(V1), append([Z1|Z],[Vnew],V2),
                                 unify_with_occurs_check(V,V2),
                                 tunify([V1|T],[Vnew],[X|S]).
tunify([V|S],Z,[X|T])     :- (S=[]; T\=[]; \+var(X)) ->
                             append(Z,[X],Z1), tunify([V|S],Z1,T).

% rules for S5
tuni_s5([],[]).
tuni_s5(S,[]) :- append(_,[X1],S), X1=[].
tuni_s5([],T) :- append(_,[X1],T), X1=[].
tuni_s5(S,T)  :- append(_,[X1],S), append(_,[X2],T),
                 unify_with_occurs_check(X1,X2).

% -----------------------------------------------------------------
% domain_cond(VariableList) - check domain condition

domain_cond(FV) :- domain(const) -> true ; domcond(FV).

domcond([]).
domcond([[X:Pre]|VarS]) :- domco(X,Pre), domcond(VarS).

domco(X,_)          :- (atomic(X);var(X);X==[[]]), !.
domco(_^_^Pre1,Pre) :- !, dom_unify(Pre1,Pre).
domco(T,Pre)        :- T=..[_,T1|T2], domco(T1,Pre), domco(T2,Pre).

dom_unify(Pre1,Pre2) :-
    domain(vary)  -> prefix_unify([-Pre1=Pre2]) ;
    domain(cumul) ->
    ( logic(s5) -> true ;
      flatten(Pre1,S), flatten(Pre2,T),
      ( logic(d)  -> length(S,LengthS), append(T1,_,T),
                     length(T1,LengthS), tuni_d(S,T1) ;
        logic(t)  -> append(T1,_,T), tuni_t(S,[],T1),
                     ( append(_,[X],T1) ->  X\==[] ; true ) ;
        logic(s4) -> append(S,[_],S1), tunify(S1,[],T)
      )
    ).
