%% File: leancop_main_transf.pl - Version: 1.0ep3 - Date: 2/03/2023
%% (12/18-02/21: only clause translation (leancop_tptp2 and def_mm)
%% (02/22: rename "=" to "equal___")
%% (03/23: use write options for ignoring operator declarations)
%%
%% Purpose: Call the leanCoP core prover for a given formula
%%
%% Authors: Jens Otten
%% Web:     www.leancop.de
%%
%% Usage:   leancop_main_trans(X,S,R,X1).
%%              % translates formula in file X with settings S into
%%              % clausal form, writes to file X2, returns result R
%%
%% Copyright: (c) 2009-2022 by Jens Otten
%% License:   GNU General Public License


:- assert(prolog(swi)).  % Prolog dialect: eclipse, sicstus, swi
:- dynamic(axiom_path/1).


% execute predicates specific to Prolog dialect

:- \+ prolog(eclipse) -> true ;
   nodbgcomp,        % switch off debugging mode
   set_flag(print_depth,10000),  % set print depth
   set_flag(variable_names,off),
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retract_all(axiom_path(_)), assert(axiom_path(Path1)),
   assert((writeCNF(S,T) :- write_term(S,T,[operators(false),
                             dotlists(false),quoted(true)]))),
   [def_mm_f]. %[leancop21].      % load leanCoP core prover

:- \+ prolog(sicstus) -> true ;
   use_module(library(system)),  % load system module
   ( environ('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   [def_mm_f]. %[leancop21_sic].  % load leanCoP core prover

:- prolog(Dialect), Dialect\=swi -> true ;
   set_prolog_flag(optimise,true),  % optimise compilation
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   assert((writeCNF(S,T) :- write_term(S,T,[ignore_ops(true),
                             quoted(true)]))),
   [def_mm_f]. %[leancop21_swi].  % load leanCoP core prover


% load additional leanCoP components

% :- [leancop_proof].  % load program for proof presentation
:- [nanocop_tptp2].  % load program for TPTP input syntax


%%% call leanCoP core prover

leancop_main_trans(File,Settings,Result,File2) :-
    axiom_path(AxPath), ( AxPath='' -> AxDir='' ;
    name(AxPath,AxL), append(AxL,[47],DirL), name(AxDir,DirL) ),
    ( leancop_tptp2(File,AxDir,[_],F,Conj) ->
      %tptp_source(F1,F,_),
      Problem=F ; [File], f(Problem), Conj=non_empty ),
    ( Conj\=[] -> Problem1=Problem ; Problem1=(~Problem) ),
    leancop_equal(Problem1,Prob2), rename_equal(Prob2,Problem2),
    make_matrix(Problem2,Matrix,Settings),
    name(File2,FL3),
    ( append([_,_,_,47],FL2,FL3)
      -> name(N,FL2), append([122,47|FL3],[46,99,110,102],FL),
         name(File3,FL) ;
      append(FL2,[46,99,110,102],FL3)
      -> name(N,FL2), File3=File2 ; N=File2, File3=File2 ),
    open(File3,write,Stream2),
%    ( append(FL2,[46,99,110,102],FL3) -> name(N,FL2) ; N=File2 ),
%    open(File2,write,Stream2),
    writeCNF(Stream2,cnf(N,conjecture,Matrix)), write(Stream2,'.'),
    close(Stream2), Result='CNF'. %, print('CNF Theorem'), nl.
% rename "=" to "equal___"

rename_equal(X,X1) :- X=='=', X1=equal___, !.
rename_equal(X,X)  :- (atomic(X);var(X);X==[[]]), !.
rename_equal(F,F1) :-
    F=..[A,B|T], rename_equal(A,A1), rename_equal(B,B1),
    rename_equal(T,T1), F1=..[A1,B1|T1].
