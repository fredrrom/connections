%% File: mleancop_main.pl  -  Version: 1.1  -  Date: 1 January 2014
%% Local notes:
%%  - added renaming: '=' -> 'equal___' in main orchestration
%%  - added tracing support through set_trace_mode/1 in prover core
%%  - merged mleancop_defmm_f behavior into mleancop_defmm.pl
%%
%% Purpose: Call the MleanCoP core prover for a given formula
%%
%% Authors: Jens Otten
%% Web:     www.leancop.de/mleancop/
%%
%% Usage:   mleancop_main(X,S,R). % proves formula in file X with
%%                                % settings S and returns result R
%%
%% Copyright: (c) 2009-2014 by Jens Otten
%% License:   GNU General Public License


:- assert(prolog(swi)).  % Prolog dialect: eclipse, sicstus, swi
:- dynamic(axiom_path/1).
:- dynamic(logic/1).
:- dynamic(domain/1).


% execute predicates specific to Prolog dialect

:- \+ prolog(eclipse) -> true ;
   nodbgcomp,        % switch off debugging mode
   set_flag(print_depth,10000),  % set print depth
   set_flag(variable_names,off),
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retract_all(axiom_path(_)), assert(axiom_path(Path1)),
   [mleancop13].      % load MleanCoP core prover

:- \+ prolog(sicstus) -> true ;
   use_module(library(system)),  % load system module
   ( environ('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   [mleancop13_sic].  % load MleanCoP core prover

:- prolog(Dialect), Dialect\=swi -> true ;
   set_prolog_flag(optimise,true),  % optimise compilation
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   [mleancop13_swi].  % load MleanCoP core prover


% load additional MleanCoP components

:- [nanocop_qmltp2].  % load program for QMLTP input syntax


%%% call MleanCoP core prover

mleancop_main(File,Settings,Result) :-
    axiom_path(AxPath), ( AxPath='' -> AxDir='' ;
    name(AxPath,AxL), append(AxL,[47],DirL), name(AxDir,DirL) ),
    ( nanocop_qmltp2(File,AxDir,[_],F,Conj) ->
      ( Conj\=[] -> Problem=F ; Problem=(~F) ),
      rename_equal(Problem,Problem1),
      make_matrix_modal(Problem1,Settings,Matrix)
      ;
      [File], f(Problem), Conj=mleancop_format,
      rename_equal(Problem,Problem1),
      ( Problem1=[_|_] -> Matrix=Problem1 ;
        make_matrix_modal(Problem1,Settings,Matrix) )
    ),
    ( prove2(Matrix,Settings,Proof) ->
      ( Conj\=[] -> Result='Theorem' ; Result='Unsatisfiable' ) ;
      ( Conj\=[] -> Result='Non-Theorem' ; Result='Satisfiable' )
    ),
    output_result(File,Proof,Result,Conj).

% print status and connection proof

output_result(File,Proof,Result,Conj) :-
    ( Conj\=[] -> Art=' is a ' ; Art=' is ' ), nl,
    logic(Logic), domain(Domain) ->
    print(File), print(Art), print('modal ('), print(Logic),
    print('/'), print(Domain), print(') '), print(Result), nl,
    ( Proof=[] -> true ; ( Result='Theorem' -> Out=' for ' ;
      Result='Unsatisfiable' -> Out=' for negated ' ; true ) ),
    ( var(Out) -> true ; print('Start of proof'), print(Out),
      print(File), nl, print(Proof), nl,  % output compact proof
      print('End of proof'), print(Out), print(File), nl ).

rename_equal(X,X1) :- X=='=', X1=equal___, !.
rename_equal(X,X)  :- (atomic(X);var(X);X==[[]]), !.
rename_equal(F,F1) :-
    F=..[A,B|T], rename_equal(A,A1), rename_equal(B,B1),
    rename_equal(T,T1), F1=..[A1,B1|T1].
