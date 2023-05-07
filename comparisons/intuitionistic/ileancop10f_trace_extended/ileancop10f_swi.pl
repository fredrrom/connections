%% Version: 1.0  -  Date: 25/11/2004  -  File: ileancop.pl
%%          1.0f -  Date: 12/12/2022  -  File: ileancop10f.pl
%%            - no re-shuffling of clauses in Mat
%%            - ground clauses are not removed from Mat
%%            - start clause not moved to beginning of Mat
%%            - path limit check also for propositional clauses
%%            - iterative deeping is always done
%%            - added extended regularity (check whole clause)
%%
%% Purpose: ileanCoP: A Connection Prover for Intuitionistic Logic
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/ileancop/
%%
%% Usage:   prove(F).   % where F is a first-order formula
%%                      %  e.g. F=((p,all X:(p=>q(X)))=>all Y:q(Y))
%%
%% Copyright: (c) 2005 by Jens Otten
%% License:   GNU General Public License


:- [def_mm_intu].
%:- dynamic(pathlim/0).

%%% prove formula F

prove(F) :- retractall(count(_)), assert(count(0)),
            Time1 is cputime, make_matrix_intu(F,M,[]), prove(M,1),
            retract(count(I)),print(successful_connections:I),nl,
            Time2 is cputime, Time is Time2-Time1, print(Time).

prove2(F,Set) :- retractall(count(_)), assert(count(0)),
                 Time1 is cputime, make_matrix_intu(F,M,Set), prove(M,1),
                 retract(count(I)),print(successful_connections:I),nl,
                 Time2 is cputime, Time is Time2-Time1, print(Time).

prove(Mat,PathLim) :- print(pathlim___________:PathLim),nl, %%%
     append(MatA,[FV:Cla|MatB],Mat), \+member(-(_):_,Cla),
     append(MatA,[FV:[-(!):(-[])|Cla]|MatB],Mat1),
     prove([!:[]],[!:[]],Mat1,[],PathLim,[PreSet,FreeV]),
     print(prefix_unify(FreeV)),nl,
     check_addco(FreeV),
%     print(check_addco_success),nl,
%     print(prefix_unify(PreSet)),nl,
     prefix_unify(PreSet),
     print(prefix_unify_success),nl.

prove(Mat,PathLim) :-
     PathLim1 is PathLim+1, prove(Mat,PathLim1).

prove([],_,_,_,_,[[],[]]).

prove([Lit:Pre|Cla],Cla4,Mat,Path,PathLim,[PreSet,FreeV]) :-
     \+ (member(LitC,Cla4), member(LitP,Path), LitC==LitP),
     (-NegLit=Lit;-Lit=NegLit) ->
        ( member(NegL:PreN,Path), unify_with_occurs_check(NegL,NegLit),
          \+ \+ prefix_unify([Pre=PreN]), PreSet1=[], FreeV3=[],
          print('  '),print(reduction_weak_prefix_unify(Pre=PreN)),nl, %%%
          print('  '),print(reduction_weak_prefix_unify_success),nl, %%%
          print(reduction(Lit:Pre,NegL:PreN)), nl,
          retract(count(I)), I1 is I+1, assert(count(I1))
          ;
          member(Cla1,Mat), copy_term(Cla1,FV:Cla2),
          length(Path,K), K<PathLim,
          append(ClaA,[NegL:PreN|ClaB],Cla2),
          unify_with_occurs_check(NegL,NegLit),
          \+ \+ prefix_unify([Pre=PreN]),
          print('  '),print(extension_weak_prefix_unify(Pre=PreN)),nl, %%%
          print('  '),print(extension_weak_prefix_unify_success),nl, %%%
          print(extension(Lit:Pre,NegL:PreN)), nl,
          retract(count(I)), I1 is I+1, assert(count(I1)),
          append(ClaA,ClaB,Cla3),
          prove(Cla3,Cla3,Mat,[Lit:Pre|Path],PathLim,[PreSet1,FreeV1]),
          append(FreeV1,FV,FreeV3)
        ),
        prove(Cla,Cla4,Mat,Path,PathLim,[PreSet2,FreeV2]),
        append([Pre=PreN|PreSet1],PreSet2,PreSet),
        append(FreeV2,FreeV3,FreeV).


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
