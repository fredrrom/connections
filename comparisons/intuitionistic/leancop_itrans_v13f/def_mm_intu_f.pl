%% File: def_mm_intu.pl  -  Version: 1.01  -  Date: 08 April 2022
%%
%% Purpose: Transform first-order formulae into the intuitionistic
%%          clausal form, in which prefixes are added to all literals
%%     changes: - pretty print skolem terms and def. predicates
%%              - add prefix to literals, and all (term) variables
%%              - represent all prefixes [a1,a2,..] as (a1,a2,..)
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/ileancop/
%%
%% Usage:   make_matrix_intu(F,M,S).  % where F is a first-order formula,
%%                                    % S is a list of settings, and M is
%%                                    % the intuitionistic clausal form
%%
%% Example: make_matrix_intu(ex Y: (all X: ((p(Y) => p(X))) ),Matrix,[]).
%%          Matrix = [[[X1,[]]] : [-(p(X1)) : -([1^[X1], 2^[X1]])],
%%                    [] : [p(1^[X1]^[1^[X1]]) : [1^[X1], 2^[X1]]]]
%%
%% Copyright: (c) 2005-2022 by Jens Otten
%% License:   GNU General Public License


% definitions of logical connectives and quantifiers

:- op(1130, xfy, <=>). % equivalence
:- op(1110, xfy, =>).  % implication
%                      % disjunction (;)
%                      % conjunction (,)
:- op( 500, fy, ~).    % negation
:- op( 500, fy, all).  % universal quantifier
:- op( 500, fy, ex).   % existential quantifier
:- op( 500,xfy, :).


% ------------------------------------------------------------------
%  make_matrix_intu(+Fml,-Matrix,+Settings)
%    -  transform first-order formula into set of clauses (matrix),
%       in which a prefix is added to every literal and a list of
%       all its prefix variables is added to every clause
%
%  Fml, Matrix: first-order formula and matrix with prefixes
%
%  Settings: list of settings, which can contain def, nodef and conj;
%            if it contains nodef/def, no definitional transformation
%            or a complete definitional transformation is done,
%            otherwise definitional transformation is done only for
%            the conjecture; conjecture is marked if conj is given
%
%  Syntax of Fml: negation '~', disjunction ';', conjunction ',',
%      implication '=>', equivalence '<=>', universal/existential
%      quantifier 'all X:<Formula>'/'ex X:<Formula>' where 'X' is a
%      Prolog variable, and atomic formulae are Prolog atoms.
%
%  Example: make_matrix_intu(ex Y:(all X:((p(Y) => p(X)))),Matrix,[]).
%           Matrix = [[[X1,[]]] : [-(p(X1)): -([1^[X1],2^[X1]])],
%                     [] : [p(1^[X1]^[1^[X1]]): [1^[X1],2^[X1]]]]

make_matrix_intu(Fml,Matrix,Set) :-
    univar(Fml,[],F1),
    ( member(conj,Set), F1=(A=>C) -> F2=((A,#)=>(#,C)) ; F2=F1 ),
    ( member(nodef,Set) ->
       def_nnf(F2,NNF,1,_,nnf), dnf(NNF,DNF)
       ;
       \+member(def,Set), F2=(B=>D) ->
        def_nnf(-(B),NNF,1,I,nnf), dnf(NNF,DNF1),
        def_nnf(D,DNF2,I,_,def), DNF=(DNF2;DNF1)
        ;
        def_nnf(F2,DNF,1,_,def)
    ),
    mat(DNF,M), M1=M, %matvar(M,M1),
    ( member(reo(I),Set) -> mreorder(M1,Matrix,I) ; Matrix=M1 ).

% ------------------------------------------------------------------
%  def_nnf(+Fml,-DEF)  -  transform formula into a definitional
%                         Skolemized negation normal form (DEF)
%  Fml, DEF: first-order formula and formula in DEF
%
%  Example: def_nnf(ex Y:(all X:((p(Y) => p(X)))),DEF,def).
%           DEF = -(p(X1^[])): [1^[X1], 2^[X1]] ;
%                 p(1^[X1]^[1^[X1]]): [1^[X1], 2^[X1]]

def_nnf(Fml,DEF,I,I1,Set) :-
    def(Fml:[],[],NNF,DEF1,_,I,I1,Set), def(DEF1,NNF,DEF).

def([],Fml,Fml).
def([(A,(B;C))|DefL],DEF,Fml) :- !, def([(A,B),(A,C)|DefL],DEF,Fml).
def([A|DefL],DEF,Fml) :- def(DefL,(A;DEF),Fml).

def(Fml:Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :-
    append([c_skolem,I],FreeV,SkPrefL), SkPref=..SkPrefL,
    ( Fml = ~A         -> Fml1 = -(A),                Pre1=[SkPref];
      %Fml = ~A         -> Fml1 = -(A),                Pre1=[I^FreeV];
      Fml = -(~A)      -> Fml1 = A,                   Pre1=[_];
      Fml = -(all X:F) -> Fml1 = (ex X: -F),          Pre1=[_];
      Fml = -(ex X:F)  -> Fml1 = (all X: -F),         Pre1=[];
      Fml = -((A ; B)) -> Fml1 = ((-A , -B)),         Pre1=[];
      Fml = -((A , B)) -> Fml1 = (-A ; -B),           Pre1=[];
      Fml = (A => B)   -> Fml1 = (-A ; B),            Pre1=[SkPref];
      %Fml = (A => B)   -> Fml1 = (-A ; B),            Pre1=[I^FreeV];
      Fml = -((A => B))-> Fml1 = ((A , -B)),          Pre1=[_];
      Fml = (A <=> B)  -> Fml1 = ((A => B),(B => A)), Pre1=[];
      Fml = -((A<=>B)) -> Fml1 = -(((A=>B),(B=>A))),  Pre1=[] ), !,
      append(Pre,Pre1,Pre2), I2 is I+1,
      ([Pre3]=Pre1, var(Pre3) -> FreeV1=[Pre3|FreeV] ; FreeV1=FreeV),
      def(Fml1:Pre2,FreeV1,NNF,DEF,Paths,I2,I1,Set).

def((ex X:F):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    PreT=..[pre|Pre],
    copy_term((X,F,FreeV),((X1:PreT),F1,FreeV)),
    def(F1:Pre,[X1|FreeV],NNF,DEF,Paths,I,I1,Set).

def((all X:Fml):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    append([f_skolem,I],FreeV,SkTermL), SkTerm=..SkTermL,
    copy_term((X,Fml,FreeV),(SkTerm:PreT,Fml1,FreeV)), I2 is I+1,
    %copy_term((X,Fml,FreeV),((I^FreeV^Pre1),Fml1,FreeV)), I2 is I+1,
    append([c_skolem,I],FreeV,SkPrefL), SkPref=..SkPrefL,
    (Fml= -_ -> Pre1=Pre ; append(Pre,[SkPref],Pre1)),
    PreT=..[pre|Pre1],
    %(Fml= -_ -> Pre1=Pre ; append(Pre,[I^FreeV],Pre1)),
    def(Fml1:Pre1,FreeV,NNF,DEF,Paths,I2,I1,Set).

def((A ; B):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    def(A:Pre,FreeV,NNF1,DEF1,Paths1,I,I2,Set),
    def(B:Pre,FreeV,NNF2,DEF2,Paths2,I2,I1,Set),
    append(DEF1,DEF2,DEF), Paths is Paths1 * Paths2,
    (Paths1 > Paths2 -> NNF = (NNF2;NNF1);
                        NNF = (NNF1;NNF2)).

def((A , B):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    def(A:Pre,FreeV,NNF3,DEF3,Paths1,I,I2,Set),
    ( NNF3=(_;_), Set=def -> append([p_defini,I2],FreeV,DfPredL2),
                             DfPred2=..DfPredL2,
                             append([((-DfPred2:pre),NNF3)],DEF3,DEF1),
                             NNF1=DfPred2:pre, I3 is I2+1 ;
                             %append([(-(I2^FreeV):[],NNF3)],DEF3,DEF1),
                             %NNF1=I2^FreeV:[], I3 is I2+1 ;
                             DEF1=DEF3, NNF1=NNF3, I3 is I2 ),
    def(B:Pre,FreeV,NNF4,DEF4,Paths2,I3,I4,Set),
    ( NNF4=(_;_), Set=def -> append([p_defini,I4],FreeV,DfPredL4),
                             DfPred4=..DfPredL4,
                             append([((-DfPred4):pre,NNF4)],DEF4,DEF2),
                             NNF2=DfPred4:pre, I1 is I4+1 ;
                             %append([(-(I4^FreeV):[],NNF4)],DEF4,DEF2),
                             %NNF2=I4^FreeV:[], I1 is I4+1 ;
                             DEF2=DEF4, NNF2=NNF4, I1 is I4 ),
    append(DEF1,DEF2,DEF), Paths is Paths1 + Paths2,
    (Paths1 > Paths2 -> NNF = (NNF2,NNF1);
                        NNF = (NNF1,NNF2)).

def(Lit:Pre,_,Lit:PreT,[],1,I,I,_) :- PreT=..[pre|Pre].

% ------------------------------------------------------------------
%  dnf(+NNF,-DNF)  -  transform formula in NNF into formula in DNF
%  NNF, DNF: formulae in NNF and DNF
%
%  Example: dnf((p:[] ; -(p):[1^[]], (q:[] ; -(q):[2^[]])),DNF).
%           DNF = p:[] ; -(p):[1^[]],q:[] ; -(p):[1^[]],-(q):[2^[]]

dnf(((A;B),C),(F1;F2)) :- !, dnf((A,C),F1), dnf((B,C),F2).
dnf((A,(B;C)),(F1;F2)) :- !, dnf((A,B),F1), dnf((A,C),F2).
dnf((A,B),F) :- !, dnf(A,A1), dnf(B,B1),
    ( (A1=(_;_);B1=(_;_)) -> dnf((A1,B1),F) ; F=(A1,B1) ).
dnf((A;B),(A1;B1)) :- !, dnf(A,A1), dnf(B,B1).
dnf(Lit,Lit).

% ------------------------------------------------------------------
%  mat(+DNF,-Matrix)  -  transform formula in DNF into matrix
%  DNF, Matrix: formula in DNF, matrix
%
%  Example: mat((p:[];-(p):[1^[]],q:[];-(p):[1^[]],-(q):[2^[]]),Mat).
%           Mat = [[p: []], [-(p): -([1^[]]), q: []],
%                  [-(p): -([1^[]]), -(q): -([2^[]])]]

mat((A;B),M) :- !, mat(A,MA), mat(B,MB), append(MA,MB,M).
mat((A,B),M) :- !, (mat(A,[CA]),mat(B,[CB]) -> union2(CA,CB,M);M=[]).
%mat(-(Lit):Pre,[[-(Lit):(-Pre)]]) :- !.
mat(Lit:Pre,[[Lit:Pre]]).

% ------------------------------------------------------------------
%  univar(+Fml,[],-Fml1)  -  rename variables
%  Fml, Fml1: first-order formulae
%
%  Example: univar((all X:(p(X) => (ex X:p(X)))),[],F1).
%           F1 = all Y : (p(Y) => ex Z : p(Z))

univar(X,_,X)  :- (atomic(X);var(X);X==[[]]), !.
univar(F,Q,F1) :-
    F=..[A,B|T], ( (A=ex;A=all) -> B=(X:C), delete2(Q,X,Q1),
    copy_term((X,C,Q1),(Y,D,Q1)), univar(D,[Y|Q],D1), F1=..[A,Y:D1] ;
    univar(B,Q,B1), univar(T,Q,T1), F1=..[A,B1|T1] ).

% ------------------------------------------------------------------
%  matvar(+Mat,-Mat1)  -  add list of [PreVar:Prefix] to each clause
%  Mat, Mat1: matrices
%
%  Example: matvar([[p(1^[]^[1^[]]):[1^[]], q(X1^[1^[]]):[1^[]]]],M).
%           M = [[[X1,[1^[]]]]:[p(1^[]^[1^[]]):[1^[]], q(X1):[1^[]]]]

%matvar([],[]).
%matvar([Cla|Mat],[FreeV:Cla1|Mat1]) :-
%    clavar(Cla,Cla1,FreeV), matvar(Mat,Mat1).
%
%clavar(Fml^Pre,Fml,[[Fml,Pre]]) :- var(Fml), !.
%clavar(Fml,Fml,[]) :- (atomic(Fml);Fml==[[]];Fml=_^_), !.
%clavar(Fml:Pre,Fml1:Pre,FreeV) :- !, clavar(Fml,Fml1,FreeV).
%clavar(Fml,Fml1,FreeV) :-
%    Fml=..[Op,Arg|ArgL],
%    clavar(Arg,Arg1,FreeV1), clavar(ArgL,ArgL1,FreeV2),
%    union2(FreeV1,FreeV2,[FreeV]), Fml1=..[Op,Arg1|ArgL1].

% ------------------------------------------------------------------
%  union2/member2 - union and member for lists without unification

union2([],L,[L]).
union2([X|L1],L2,M) :- member2(X,L2), !, union2(L1,L2,M).
union2([X:Pre|_],L2,M) :-
    (-(Xn)=X;-(X)=Xn) -> member2(Xn:Pre,L2), !, M=[].
    %(-(Xn):(-Pr)=X:Pre;-(X):(-Pre)=Xn:Pr) -> member2(Xn:Pr,L2), !, M=[].
union2([X|L1],L2,M) :- union2(L1,[X|L2],M).

member2(X,[Y|_]) :- X==Y, !.
member2(X,[_|T]) :- member2(X,T).

% ------------------------------------------------------------------
%  delete2 - delete variable from list

delete2([],_,[]).
delete2([X|T],Y,T1) :- X==Y, !, delete2(T,Y,T1).
delete2([X|T],Y,[X|T1]) :- delete2(T,Y,T1).

% ------------------------------------------------------------------
%  mreorder - reorder clauses

mreorder(M,M,0) :- !.
mreorder(M,M1,I) :-
    length(M,L), K is L//3, append(A,D,M), length(A,K),
    append(B,C,D), length(C,K), mreorder2(C,A,B,M2), I1 is I-1,
    mreorder(M2,M1,I1).

mreorder2([],[],C,C).
mreorder2([A|A1],[B|B1],[C|C1],[A,B,C|M1]) :- mreorder2(A1,B1,C1,M1).
