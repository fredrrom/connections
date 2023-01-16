%% Version: 1.03  -  Date: 25/11/99  -  File: leancop_swi.pl
%%          1.03b -  Date: 16/02/21  -  File: leancop10b_swi.pl
%%          (added regularity, no re-shuffling of clauses in Mat,
%%           ground clauses are not removed from Mat)
%%          1.03c -  Date: ... - File: leancop10c_swi.pl
%%          (do not move start clause to beginning of matrix,
%%           path limit check also for propositional clauses,
%%           no regularity, iterative deeping is always done)
%%          1.03f - Date: 25/11/22 (1.03c with extended regularity)
%%
%% Purpose: leanCoP: A Clausal Connection Prover for Classical Logic
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de
%%
%% Usage:   prove(M).   % where M is a set of clauses
%%                      %  e.g. M=[[q(a)],[-p],[p, -q(X)]]
%%          prove(F).   % where F is a first-order formula
%%                      %  e.g. F=((p,all X:(p=>q(X)))=>all Y:q(Y))
%%                      %  (file nnf_mm.pl is needed)
%%
%% Copyright: (c) 2001 by Jens Otten
%% License:   GNU General Public License


:- lib(iso).
:- dynamic(count/1).

%%% prove matrix M / formula F

prove([C|M]) :- retract_all(count(_)), assert(count(0)),
                !, Time1 is cputime, prove([C|M],1),
%                retract(count(I)),print(successful_connections:I),nl,
                Time2 is cputime, Time is Time2-Time1, print(Time).

prove(F) :- retract_all(count(_)), assert(count(0)),
            Time1 is cputime, make_matrix(F,M,[]), prove(M,1),
%            retract(count(I)),print(successful_connections:I),nl,
            Time2 is cputime, Time is Time2-Time1, print(Time).

prove2(F,Set) :- retract_all(count(_)), assert(count(0)),
                 Time1 is cputime, make_matrix(F,M,Set), prove(M,1),
%                 retract(count(I)),print(successful_connections:I),nl,
                 Time2 is cputime, Time is Time2-Time1, print(Time).

prove(Mat,PathLim) :-
     append(MatA,[Cla|MatB],Mat), \+member(-_,Cla),
     append(MatA,[[-!|Cla]|MatB],Mat1),
     prove([!],[!],Mat1,[],PathLim).

prove(Mat,PathLim) :-
     PathLim1 is PathLim+1, prove(Mat,PathLim1).

prove([],_,_,_,_).

prove([Lit|Cla],Cla4,Mat,Path,PathLim) :-
     \+ (member(LitC,Cla4), member(LitP,Path), LitC==LitP),
     (-NegLit=Lit;-Lit=NegLit) ->
        ( member(NegL,Path), unify_with_occurs_check(NegL,NegLit),
%%          print(reduction(Lit,NegL)), nl,
          retract(count(I)), I1 is I+1, assert(count(I1))
          ;
          member(Cla1,Mat), copy_term(Cla1,Cla2),
          length(Path,K), K<PathLim,
          append(ClaA,[NegL|ClaB],Cla2),
          unify_with_occurs_check(NegL,NegLit),
%%          print(extension(Lit,NegL)), nl,
          retract(count(I)), I1 is I+1, assert(count(I1)),
          append(ClaA,ClaB,Cla3),
          prove(Cla3,Cla3,Mat,[Lit|Path],PathLim)
        ),
        prove(Cla,Cla4,Mat,Path,PathLim).

