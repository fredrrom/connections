%% ----------
%% File:    leancop_tlimit.pl
%% Version: 1.0 (for ECLiPSe Prolog)
%% Date:    1 July 2007
%% ----------
%% Purpose: Invokes the leanCoP series theorem provers with a time limit
%% Author:  Jens Otten
%% Web:     www.leancop.de
%% ----------

:- nodbgcomp, dynamic(time_limit/1).

leancop_tlimit(Prover,Settings,ProblemFile,TimeLimit) :-
    set_event_handler(time_up,time_up/0),
    event_after_every(time_up,2),
    assert(time_limit(TimeLimit)),
    [Prover],
    [ProblemFile],
    f(Problem),
    prove2(Problem,Settings).

time_up :-
    time_limit(TimeLimit),
    cputime(Time),
    ( Time < TimeLimit -> true ; exit(2) ).
