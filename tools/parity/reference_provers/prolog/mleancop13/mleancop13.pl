%% File: mleancop13.pl  -  Version: 1.3  -  Date: 1 January 2014
%%
%%         "Make everything as simple as possible, but not simpler."
%%                                                 [Albert Einstein]
%%
%% Purpose: MleanCoP: A Connection Prover for Modal Logic
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/mleancop/
%%
%% Usage:   prove(F,P).      % where F is a modal first-order formula
%%                           %  and P is the returned connection proof
%%                           %  e.g. F=((# all X:p(X)) => all X: #p(X))
%%                           %  and  P=[[p(3^[]^[]):[4^[]]],
%%                           %         [[-(p(3^[]^[])):-([[4^[]]])]]]
%%          prove2(F,S,P).   % where F is a formula, S is a subset of
%%                           %  [nodef,def,conj,reo(I),scut,cut,comp(J)]
%%                           %  (with numbers I,J) defining attributes
%%                           %  and P is the returned connection proof
%%
%% Copyright: (c) 2011-2014 by Jens Otten
%% License:   GNU General Public License

logic(s4).       % specify modal logic (d,t,s4,s5,multi)
domain(cumul).   % specify domain condition (const,cumul,vary)


:- lib(iso).                   % load library for ISO compatibility
:- set_flag(occur_check,on).   % global occur check on
:- [mleancop_defmm].           % load program for clausal form translation
:- dynamic(pathlim/0), dynamic(lit/3).

%%% prove formula F

prove(F,Proof) :- prove2(F,[scut,cut,comp(7)],Proof).

prove2(F,Set,Proof) :-
    (F=[_|_] -> M=F ; make_matrix_modal(F,Set,M)),
    retract_all(lit(_,_,_)), (member([(-(#)):_],M) -> S=conj ; S=pos),
    assert_clauses(M,S), prove(1,Set,Proof).

prove(PathLim,Set,Proof) :-
    ( \+member(scut,Set) ->
      prove([(-(#)):(-[])],[],PathLim,[],PreSet,FreeV1,Set,[Proof]) ;
      lit((#):_,FV:C,_) ->
      prove(C,[(-(#)):(-[])],PathLim,[],PreSet,FreeV,Set,Proof1),
      Proof=[C|Proof1], append(FreeV,FV,FreeV1) ),
      domain_cond(FreeV1), prefix_unify(PreSet).
prove(PathLim,Set,Proof) :-
    member(comp(Limit),Set), PathLim=Limit -> prove(1,[],Proof) ;
    (member(comp(_),Set);retract(pathlim)) ->
    PathLim1 is PathLim+1, prove(PathLim1,Set,Proof).

%%% MleanCoP core prover

prove([],_,_,_,[],[],_,[]).

prove([Lit:Pre|Cla],Path,PathLim,Lem,PreSet,FreeV,Set,Proof) :-
    Proof=[[[NegLit:PreN|Cla1]|Proof1]|Proof2],
    \+ (member(LitC,[Lit:Pre|Cla]), member(LitP,Path), LitC==LitP),
    (-NegLit=Lit;-Lit=NegLit) ->
       ( member(LitL,Lem), Lit:Pre==LitL, Cla1=[], Proof1=[],
         PreSet3=[], FreeV3=[]
         ;
         member(NegL:PreN,Path), unify_with_occurs_check(NegL,NegLit),
         Cla1=[], Proof1=[],
         \+ \+ prefix_unify([Pre=PreN]), PreSet3=[Pre=PreN], FreeV3=[]
         ;
         lit(NegLit:PreN,FV:Cla1,Grnd1),
         ( Grnd1=g -> true ; length(Path,K), K<PathLim -> true ;
           \+ pathlim -> assert(pathlim), fail ),
         \+ \+ ( domain_cond(FV), prefix_unify([Pre=PreN]) ),
         prove(Cla1,[Lit:Pre|Path],PathLim,Lem,PreSet1,FreeV1,Set,Proof1),
         PreSet3=[Pre=PreN|PreSet1], append(FreeV1,FV,FreeV3)
       ),
       ( member(cut,Set) -> ! ; true ),
       prove(Cla,Path,PathLim,[Lit:Pre|Lem],PreSet2,FreeV2,Set,Proof2),
       append(PreSet3,PreSet2,PreSet), append(FreeV2,FreeV3,FreeV).

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


%%% prefix unification for D, T, S4, S5, multimodal

prefix_unify([]).
prefix_unify([S=T|G]) :-
    ( -S2=S -> T2=T ; -S2=T, T2=S ),
    ( logic(s5)    -> S1=S2, T1=T2 ;
      logic(multi) -> flatten_mp(S2,S1,[],[]), flatten_mp(T2,T1,[],[]) ;
                      flatten(S2,S1), flatten(T2,T1) ),
    logic(Logic) -> prefix_unifyL(S1,T1,Logic), prefix_unify(G).

prefix_unifyL(S,T,Logic) :-
    ( Logic=multi -> tuni_multi(S,T,unify) ;
      Logic=d     -> tuni_d(S,T) ;
      Logic=t     -> tuni_t(S,[],T) ;
      Logic=s4    -> tunify(S,[],T) ;
      Logic=s5    -> tuni_s5(S,T) ).

%%% rules for D

tuni_d([],[]).
tuni_d([X1|S],[X2|T]) :- unify_with_occurs_check(X1,X2), tuni_d(S,T).

%%% rules for T

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

%%% rules for S4

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

%%% rules for S5

tuni_s5([],[]).
tuni_s5(S,[]) :- append(_,[X1],S), X1=[].
tuni_s5([],T) :- append(_,[X1],T), X1=[].
tuni_s5(S,T)  :- append(_,[X1],S), append(_,[X2],T),
                 unify_with_occurs_check(X1,X2).

%%% multimodal logic

tuni_multi([],[],_) :- !.
tuni_multi(S,T,Type) :-
    ( S=[(I^L)^_|_] -> tuni_mulpre(S,I,S1,S2) ; S1=[], S2=[], I=I1, L=L1 ),
    ( T=[(I1^L1)^_|_] -> tuni_mulpre(T,I,T1,T2) ; T1=[], T2=[] ),
    ( Type=cumul, dom_unifyLcu(S1,T1,L), tuni_multi(S2,[],unify) ;
      tuni_multi(S2,T2,Type), prefix_unifyL(S1,T1,L) ).

tuni_mulpre([],I,[],[]) :- I\=_^skip.
tuni_mulpre([(J^L)^Pre|S],I,S1,S2) :-
    (I=J^skip;I=J) -> ( ( var(Pre) ; Pre=[] ) -> S1=[Pre|S3] ;
                        S1=[(J^L)^Pre|S3] ), tuni_mulpre(S,J,S3,S2) ;
    I=_^skip -> ( ( L=t ; L=s4 ; L=s5,S\=[(J^_)^_|_] ) ->  Pre=[] ; L=s5 ),
                S1=[(J^L)^Pre|S3], tuni_mulpre(S,I,S3,S2) ;
    S1=[], S2=[(J^L)^Pre|S] ; tuni_mulpre([(J^L)^Pre|S],I^skip,S1,S2).

flatten_mp(A,[IL^A|B],B,IL) :- var(A), !.
flatten_mp(IL^Pre,[IL^Pre|B],B,_) :-
    ( var(Pre) ; Pre=P^_,P\=_^_ ; IL^Pre=(_^s5)^[] ), !.
flatten_mp(IL^A,B,D,_) :- flatten_mp(A,B,D,IL).
flatten_mp([],A,A,_).
flatten_mp([A|B],C,D,IL) :- flatten_mp(A,C,E,IL), flatten_mp(B,E,D,IL).

%%% check domain condition

domain_cond(FV) :- domain(const) -> true ; domcond(FV,FV).

domcond([],_).
domcond([[X,Pre]|L],FV) :- domco(X,Pre,FV), domcond(L,FV).

domco(X,_,_)    :- (atomic(X);X==[[]]), !.
domco(X,Pre,FV) :- var(X), !, ( \+ domain(vary) -> true ;
                   domcom(X,FV,Pre1), dom_unify(Pre1,Pre) ).
domco(_^_^Pre1,Pre,_) :- !, dom_unify(Pre1,Pre).
domco(T,Pre,FV) :- T=..[_,U|V], domco(U,Pre,FV), domco(V,Pre,FV).

domcom(X,[[X1,Pre1]|FV],Pre) :- X==X1 -> Pre=Pre1 ; domcom(X,FV,Pre).

dom_unify(Pre1,Pre2) :-
    ( logic(s5)    -> S=Pre1, T=Pre2 ;
      logic(multi) -> flatten_mp(Pre1,S,[],[]), flatten_mp(Pre2,T,[],[]) ;
                      flatten(Pre1,S), flatten(Pre2,T) ), logic(Logic) ->
    ( domain(vary)  -> prefix_unifyL(S,T,Logic) ;
      domain(cumul) -> dom_unifyLcu(S,T,Logic) ).

dom_unifyLcu(S,T,Logic) :-
      ( Logic=multi -> tuni_multi(S,T,cumul) ;
        Logic=d     -> length(S,LenS), append(T1,_,T), length(T1,LenS),
                       tuni_d(S,T1) ;
        Logic=t     -> append(T1,_,T), tuni_t(S,[],T1),
                       ( append(_,[X],T1) ->  X\==[] ; true ) ;
        Logic=s4    -> append(S,[_],S1), tunify(S1,[],T) ;
        Logic=s5    -> true ).
