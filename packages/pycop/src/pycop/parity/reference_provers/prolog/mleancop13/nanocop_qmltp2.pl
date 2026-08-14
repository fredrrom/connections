%% File: nanocop_qmltp2.pl  -  Version: 1.0  -  Date: 17 May 2017
%%
%% Purpose: Translate formula from QMLTP into modal nanoCoP syntax
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/nanocop-m/
%%
%% Usage: nanocop_qmltp2(X,F). % where X is a problem file in QMLTP
%%                             %  syntax and F the translated formula
%%
%% Copyright: (c) 2017 by Jens Otten
%% License:   GNU General Public License


% definitions of logical connectives and quantifiers

% modal nanoCoP syntax
:- op(1130, xfy, <=>). % equivalence
:- op(1110, xfy, =>).  % implication
%                      % disjunction (;)
%                      % conjunction (,)
:- op( 500, fy, #).    % box operator
:- op( 500, fy, *).    % diamond operator
:- op( 500, fy, ~).    % negation
:- op( 500, fy, all).  % universal quantifier
:- op( 500, fy, ex).   % existential quantifier
:- op( 500,xfy, :).

% QMLTP syntax
:- op(1130, xfy, <~>).  % negated equivalence
:- op(1110, xfy, <=).   % implication
:- op(1100, xfy, '|').  % disjunction
:- op(1100, xfy, '~|'). % negated disjunction
:- op(1000, xfy, &).    % conjunction
:- op(1000, xfy, ~&).   % negated conjunction
:- op( 500, fy, !).     % universal quantifier
:- op( 500, fy, ?).     % existential quantifier
:- op( 400, xfx, =).    % equality
:- op( 300, xf, !).     % negated equality (for !=)
:- op( 299, fx, $).     % for $true/$false

% QMLTP/TPTP syntax to modal nanoCoP syntax mapping

op_tptp2((A<=>B),(A1<=>B1),   [A,B],[A1,B1]).
op_tptp2((A<~>B),~((A1<=>B1)),[A,B],[A1,B1]).
op_tptp2((A=>B),(A1=>B1),     [A,B],[A1,B1]).
op_tptp2((A<=B),(B1=>A1),     [A,B],[A1,B1]).
op_tptp2((A|B),(A1;B1),       [A,B],[A1,B1]).
op_tptp2((A'~|'B),~((A1;B1)), [A,B],[A1,B1]).
op_tptp2((A&B),(A1,B1),       [A,B],[A1,B1]).
op_tptp2((A~&B),~((A1,B1)),   [A,B],[A1,B1]).
op_tptp2(~A,~A1,[A],[A1]).
op_tptp2((#box:A),(#A1),[A],[A1]).
op_tptp2((#dia:A),(*A1),[A],[A1]).
op_tptp2((! [V]:A),(all V:A1),     [A],[A1]).
op_tptp2((! [V|Vars]:A),(all V:A1),[! Vars:A],[A1]).
op_tptp2((? [V]:A),(ex V:A1),      [A],[A1]).
op_tptp2((? [V|Vars]:A),(ex V:A1), [? Vars:A],[A1]).
op_tptp2($true,(true___=>true___),      [],[]).
op_tptp2($false,(false___ , ~ false___),[],[]).
op_tptp2(A=B,~(A1=B),[],[]) :- \+var(A), A=(A1!).
op_tptp2(P,P,[],[]).


%%% translate into modal nanoCoP syntax

nanocop_qmltp2(File,F) :- nanocop_qmltp2(File,'',[_],F,_).

nanocop_qmltp2(File,AxPath,AxNames,F,Con) :-
    open(File,read,Stream), ( qmf2cop(Stream,AxPath,AxNames,A,Con)
    -> close(Stream) ; close(Stream), fail ),
    ( Con=[] -> F=A ; A=[] -> F=Con ; F=(A=>Con) ).

qmf2cop(Stream,AxPath,AxNames,F,Con) :-
    read(Stream,Term),
    ( Term=end_of_file -> F=[], Con=[] ;
      ( Term=..[qmf,Name,Type,Fml|_] ->
        ( \+member(Name,AxNames) -> true ; fml2cop([Fml],[Fml1]) ),
        ( Type=conjecture -> Con=Fml1 ; Con=Con1 ) ;
        ( Term=include(File), AxNames2=[_] ;
          Term=include(File,AxNames2) ) -> name(AxPath,AL),
          name(File,FL), append(AL,FL,AxL), name(AxFile,AxL),
          nanocop_qmltp2(AxFile,'',AxNames2,Fml1,_), Con=Con1
      ), qmf2cop(Stream,AxPath,AxNames,F1,Con1),
      ( Term=..[qmf,N,Type|_], (Type=conjecture;\+member(N,AxNames))
      -> (F1=[] -> F=[] ; F=F1) ; (F1=[] -> F=Fml1 ; F=(Fml1,F1)) )
    ).

fml2cop([],[]).
fml2cop([F|Fml],[F1|Fml1]) :-
    op_tptp2(F,F1,FL,FL1) -> fml2cop(FL,FL1), fml2cop(Fml,Fml1).

