%% File: mleancop_defmm.pl  -  Version: 1.01  -  Date: 1 May 2023
%%
%% Purpose: Transform modal first-order formulae into the modal
%%          clausal form, in which prefixes are added to all literals
%%
%% Author:  Jens Otten
%% Web:     www.leancop.de/mleancop/
%%
%% Usage:   make_matrix_modal(F,S,M). % where F is a modal first-order
%%                                    % formula, S is a list of settings,
%%                                    % and M is the modal clausal form
%%
%% Example: make_matrix_modal(((# all X:p(X)) => all X: #p(X)),[],Matrix).
%%          Matrix = [[] : [p(3^[]^[]) : [4^[]]],
%%                   [[X1,[V]]] : [-(p(X1)) : -([V])]]
%%
%% Copyright: (c) 2011-2023 by Jens Otten
%% License:   GNU General Public License


% definitions of logical connectives and quantifiers

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


% ------------------------------------------------------------------
%  make_matrix_modal(+Fml,+Settings,-Matrix)
%    -  transform first-order formula into set of clauses (matrix),
%       in which a prefix is added to every literal and a list of
%       all its prefix variables is added to every clause
%
%  Fml, Matrix: modal first-order formula and matrix with prefixes
%
%  Settings: list of settings, which can contain def, nodef and conj;
%            if it contains nodef/def, no definitional transformation
%            or a complete definitional transformation is done,
%            otherwise definitional transformation is done only for
%            the conjecture; conjecture is marked if conj is given
%
%  Syntax of Fml: negation '~', modal box operator '#', modal
%      diamond operator '*', disjunction ';', conjunction ',',
%      implication '=>', equivalence '<=>', universal/existential
%      quantifier 'all X:<Formula>'/'ex X:<Formula>' where 'X' is a
%      Prolog variable, and atomic formulae are Prolog atoms.
%
%  Example: make_matrix_modal(((# all X:p(X)) => all X: #p(X)),[],Matrix).
%           Matrix= [[]:[p(3^[]^[]):[4^[]]],[[X1,[V]]]:[-(p(X1)): -([V])]]

make_matrix_modal(Fml,Set,Matrix) :-
    univar(Fml,[],F1),
    ( member(conj,Set), F1=(A=>C) -> F2=((A,#)=>(#,C)) ; F2=F1 ),
    ( member(nodef,Set) ->
       def_nnf(F2,NNF,1,_,nnf), dnf(NNF,DNF)
       ;
       \+member(def,Set), F2=(B=>D) ->
        def_nnf(-(B),NNF,1,J,nnf), dnf(NNF,DNF1),
        def_nnf(D,DNF2,J,_,def), DNF=(DNF2;DNF1)
        ;
        def_nnf(F2,DNF,1,_,def)
    ),
    mat(DNF,M), matvar(M,M1),
    ( member(reo(I),Set) -> mreorder(M1,Matrix,I) ; Matrix=M1 ).

% ------------------------------------------------------------------
%  def_nnf(+Fml,-DEF)  -  transform formula into a definitional
%                         Skolemized negation normal form (DEF)
%  Fml, DEF: modal first-order formula and formula in DEF
%
%  Example: def_nnf(((# all X:p(X)) => all X: #p(X)),DEF,0,_,def).
%           DEF = -(p(X1^[V])): [V] ; p(3^[]^[]): [4^[]]

def_nnf(Fml,DEF,I,I1,Set) :-
    def(Fml:[],[],NNF,DEF1,_,I,I1,Set), def(DEF1,NNF,DEF).

def([],Fml,Fml).
def([(A,(B;C))|DefL],DEF,Fml) :- !, def([(A,B),(A,C)|DefL],DEF,Fml).
def([A|DefL],DEF,Fml) :- def(DefL,(A;DEF),Fml).

def(Fml:Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :-
    ( Fml = (#A)       -> Fml1 = A,                   Pre1=[I^FreeV];
      Fml = -(#A)      -> Fml1 = -(A),                Pre1=[_];
      Fml = (*A)       -> Fml1 = A,                   Pre1=[_];
      Fml = -(*A)      -> Fml1 = -(A),                Pre1=[I^FreeV];
      Fml = (~A)       -> Fml1 = -(A),                Pre1=[];
      Fml = -(~A)      -> Fml1 = A,                   Pre1=[];
      Fml = -(all X:F) -> Fml1 = (ex X: -F),          Pre1=[];
      Fml = -(ex X:F)  -> Fml1 = (all X: -F),         Pre1=[];
      Fml = -((A ; B)) -> Fml1 = ((-A , -B)),         Pre1=[];
      Fml = -((A , B)) -> Fml1 = (-A ; -B),           Pre1=[];
      Fml = (A => B)   -> Fml1 = (-A ; B),            Pre1=[];
      Fml = -((A => B))-> Fml1 = ((A , -B)),          Pre1=[];
      Fml = (A <=> B)  -> Fml1 = ((A => B),(B => A)), Pre1=[];
      Fml = -((A<=>B)) -> Fml1 = -(((A=>B),(B=>A))),  Pre1=[] ), !,
      append(Pre,Pre1,Pre2), I2 is I+1,
      ([Pre3]=Pre1, var(Pre3) -> FreeV1=[Pre3|FreeV] ; FreeV1=FreeV),
      def(Fml1:Pre2,FreeV1,NNF,DEF,Paths,I2,I1,Set).

def((ex X:F):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    copy_term((X,F,FreeV),((X1^Pre),F1,FreeV)),
    def(F1:Pre,[X1|FreeV],NNF,DEF,Paths,I,I1,Set).

def((all X:Fml):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    copy_term((X,Fml,FreeV),((I^FreeV^Pre),Fml1,FreeV)), I2 is I+1,
    def(Fml1:Pre,FreeV,NNF,DEF,Paths,I2,I1,Set).

def((A ; B):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    def(A:Pre,FreeV,NNF1,DEF1,Paths1,I,I2,Set),
    def(B:Pre,FreeV,NNF2,DEF2,Paths2,I2,I1,Set),
    append(DEF1,DEF2,DEF), Paths is Paths1 * Paths2,
    (Paths1 > Paths2 -> NNF = (NNF2;NNF1);
                        NNF = (NNF1;NNF2)).

def((A , B):Pre,FreeV,NNF,DEF,Paths,I,I1,Set) :- !,
    def(A:Pre,FreeV,NNF3,DEF3,Paths1,I,I2,Set),
    ( NNF3=(_;_), Set=def -> append([(-(I2^FreeV):[],NNF3)],DEF3,DEF1),
                             NNF1=I2^FreeV:[], I3 is I2+1 ;
                             DEF1=DEF3, NNF1=NNF3, I3 is I2 ),
    def(B:Pre,FreeV,NNF4,DEF4,Paths2,I3,I4,Set),
    ( NNF4=(_;_), Set=def -> append([(-(I4^FreeV):[],NNF4)],DEF4,DEF2),
                             NNF2=I4^FreeV:[], I1 is I4+1 ;
                             DEF2=DEF4, NNF2=NNF4, I1 is I4 ),
    append(DEF1,DEF2,DEF), Paths is Paths1 + Paths2,
    (Paths1 > Paths2 -> NNF = (NNF2,NNF1);
                        NNF = (NNF1,NNF2)).

def(Lit,_,Lit,[],1,I,I,_).

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
mat(-(Lit):Pre,[[-(Lit):(-Pre)]]) :- !.
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

matvar([],[]).
matvar([Cla|Mat],[FreeV:Cla1|Mat1]) :-
    clavar(Cla,Cla1,FreeV), matvar(Mat,Mat1).

clavar(Fml^Pre,Fml,[[Fml,Pre]]) :- var(Fml), !.
clavar(Fml,Fml,[]) :- (atomic(Fml);Fml==[[]];Fml=_^_), !.
clavar(Fml:Pre,Fml1:Pre,FreeV) :- !, clavar(Fml,Fml1,FreeV).
clavar(Fml,Fml1,FreeV) :-
    Fml=..[Op,Arg|ArgL],
    clavar(Arg,Arg1,FreeV1), clavar(ArgL,ArgL1,FreeV2),
    union2(FreeV1,FreeV2,[FreeV]), Fml1=..[Op,Arg1|ArgL1].

% ------------------------------------------------------------------
%  union2/member2 - union and member for lists without unification

union2([],L,[L]).
union2([X|L1],L2,M) :- member2(X,L2), !, union2(L1,L2,M).
union2([X:Pre|_],L2,M) :-
    (-(Xn):(-Pr)=X:Pre;-(X):(-Pre)=Xn:Pr) -> member2(Xn:Pr,L2), !, M=[].
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
    length(M,L), K is L//3, mreorder1(M,A,D,K), mreorder1(D,B,C,K),
    mreorder2(C,A,B,M2), I1 is I-1, mreorder(M2,M1,I1).

mreorder1(M,[],M,0) :- !.
mreorder1([C|M],[C|M1],M2,I) :- I1 is I-1, mreorder1(M,M1,M2,I1).

mreorder2(C,[],[],C).
mreorder2([A|A1],[B|B1],[C|C1],[A,B,C|M1]) :- mreorder2(A1,B1,C1,M1).
