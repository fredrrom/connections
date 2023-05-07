%% File: mleancop10_main.pl  -  Version: 1.0  -  Date: 5 Dec 2022
%%
%% Purpose: Call the MleanCoP core prover for a given formula
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/mleancop/
%%
%% Usage:   mleancop10_main(X,S,R). % prove formula in file X with
%%                                %  settings S and returns result R
%%
%% Copyright: (c) 2017-2022 by Jens Otten
%% License:   GNU General Public License

:- assert(prolog(swi)).  % Prolog dialect (eclipse/swi)
:- dynamic(axiom_path/1).
:- dynamic(logic/1).
:- dynamic(domain/1).

% execute predicates specific to Prolog dialect

:- \+ prolog(eclipse) -> true ;
   nodbgcomp,  % switch off debugging mode
   set_flag(print_depth,10000),  % set print depth
   set_flag(variable_names,off),  % print internal variable names
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retract_all(axiom_path(_)), assert(axiom_path(Path1)),
   %[mleancop_def_mm],
   [mleancop10f].  % load leanCoP core prover

:- prolog(eclipse) -> true ;
   style_check(-singleton),
   set_prolog_flag(print_write_options,[quoted(false)]),
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   %[mleancop_def_mm],
   [mleancop10f_swi].  % load leanCoP core prover

% load additional nanoCoP-i components

:- [nanocop_qmltp2].  % load module to support QMLTP syntax

%%% call the nanoCoP-i core prover

mleancop10_main(File,Settings,Result) :-
    axiom_path(AxPath), ( AxPath='' -> AxDir='' ;
    name(AxPath,AxL), append(AxL,[47],DirL), name(AxDir,DirL) ),
    ( nanocop_qmltp2(File,AxDir,[_],F,Conj) ->
      Problem=F ; [File], f(Problem), Conj=non_empty ),
    ( Conj\=[] -> Problem2=Problem ; Problem2=(~Problem) ),
    %( member(noeq,Settings) -> Problem1=Problem2 ;
    %    leancop_equal(Problem1,Problem2) ),
    %%rename_equal(Problem2a,Problem2),
    ( %prove2(Problem2,Settings,Proof) ->
      prove2(Problem2,Settings) ->
      ( Conj\=[] -> Result='Theorem' ; Result='Unsatisfiable' ) ;
      ( Conj\=[] -> Result='Non-Theorem' ; Result='Satisfiable' )
    ),
    %make_matrix_modal(Problem2,Matrix,Settings),
    output_result(File,Matrix,Proof,Result,Conj).

% print status and connection proof

output_result(File,Matrix,Proof,Result,Conj) :-
    ( Conj\=[] -> Art=' is a ' ; Art=' is ' ), nl,
    ( logic(Logic), domain(Domain) -> true ),
    print(File), print(Art), print('modal ('), print(Logic),
    print('/'), print(Domain), print(') '), print(Result), nl.

%rename_equal(X,X1) :- X=='=', X1=equal___, !.
%rename_equal(X,X)  :- (atomic(X);var(X);X==[[]]), !.
%rename_equal(F,F1) :-
%    F=..[A,B|T], rename_equal(A,A1), rename_equal(B,B1),
%    rename_equal(T,T1), F1=..[A1,B1|T1].
