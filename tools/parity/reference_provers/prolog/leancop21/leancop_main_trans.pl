%% File: leancop_main_transf.pl - Version: 1.0ep3 - Date: 2/03/2023
%% Local notes:
%%  - added renaming: '=' -> 'equal___' during translation output
%%  - merged def_mm_f behavior into def_mm.pl
%%  - kept translator output formatting options for CNF serialization
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
:- dynamic(trace_mode/1).

trace_mode(off).

set_trace_mode(Mode) :-
    retractall(trace_mode(_)),
    assertz(trace_mode(Mode)).

trace_event(_) :-
    \+ trace_mode(on),
    !.
trace_event(Event) :-
    write(Event), nl.


% execute predicates specific to Prolog dialect

:- \+ prolog(eclipse) -> true ;
   nodbgcomp,        % switch off debugging mode
   set_flag(print_depth,10000),  % set print depth
   set_flag(variable_names,off),
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retract_all(axiom_path(_)), assert(axiom_path(Path1)),
   assert((writeCNF(S,T) :- write_term(S,T,[operators(false),
                             dotlists(false),quoted(true)]))),
   [def_mm]. %[leancop21].      % load leanCoP core prover

:- \+ prolog(sicstus) -> true ;
   use_module(library(system)),  % load system module
   ( environ('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   [def_mm]. %[leancop21_sic].  % load leanCoP core prover

:- prolog(Dialect), Dialect\=swi -> true ;
   set_prolog_flag(optimise,true),  % optimise compilation
   ( getenv('TPTP',Path) -> Path1=Path ; Path1='' ),
   retractall(axiom_path(_)), assert(axiom_path(Path1)),
   assert((writeCNF(S,T) :- write_term(S,T,[ignore_ops(true),
                             quoted(true)]))),
   [def_mm]. %[leancop21_swi].  % load leanCoP core prover


% load additional leanCoP components

% :- [leancop_proof].  % load program for proof presentation
:- [leancop_tptp2].  % load program for TPTP input syntax


%%% call leanCoP core prover

leancop_main_trans(File,Settings,Result,File2) :-
    trace_event('matrix.from_file.start'),
    axiom_path(AxPath), ( AxPath='' -> AxDir='' ;
    name(AxPath,AxL), append(AxL,[47],DirL), name(AxDir,DirL) ),
    ( leancop_tptp2(File,AxDir,[_],F,Conj) ->
      %tptp_source(F1,F,_),
      Problem=F ; [File], f(Problem), Conj=non_empty ),
    trace_event('clausification.document.start'),
    ( Conj\=[] -> Problem1=Problem ; Problem1=(~Problem) ),
    trace_event('clausification.document.roles'),
    trace_event('clausification.document.combine'),
    trace_event('clausification.formula.start'),
    trace_event('clausification.equality_axioms'),
    leancop_equal(Problem1,Prob2), rename_equal(Prob2,Problem2),
    trace_event('clausification.univar'),
    trace_defmm_events(Settings,Problem2),
    make_matrix(Problem2,Matrix,Settings),
    trace_event('clausification.mat'),
    ( member(reo(_),Settings) -> trace_event('clausification.reorder') ; true ),
    trace_event('clausification.done'),
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
    close(Stream2), trace_event('matrix.from_file.done'), Result='CNF'. %, print('CNF Theorem'), nl.

trace_defmm_events(Settings,Formula) :-
    ( member(nodef,Settings) ->
      trace_event('clausification.def_nnf'),
      trace_event('clausification.dnf')
    ; member(def,Settings) ->
      trace_event('clausification.def_nnf')
    ; Formula=(_=>_) ->
      trace_event('clausification.def_nnf'),
      trace_event('clausification.dnf'),
      trace_event('clausification.def_nnf')
    ; trace_event('clausification.def_nnf') ).
% rename "=" to "equal___"

rename_equal(X,X1) :- X=='=', X1=equal___, !.
rename_equal(X,X)  :- (atomic(X);var(X);X==[[]]), !.
rename_equal(F,F1) :-
    F=..[A,B|T], rename_equal(A,A1), rename_equal(B,B1),
    rename_equal(T,T1), F1=..[A1,B1|T1].
