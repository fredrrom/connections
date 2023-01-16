#!/bin/sh
#-----------
# leancop10b.sh, v1.0b (16 Feb 2021)
#-----------
# Purpose:  Invokes leanCoP 1.0
# Usage:    ./leancop10b.sh <problem file>
#-----------

#-----------
# Parameters

PROVER=leancop10c_swi.pl

PROLOG_PATH=swipl
#PROLOG_OPTIONS='-nodebug -L120M -G120M -T100M -q -g'
PROLOG_OPTIONS='-g'

#------cvccc    -------
# Main Program

if [ $# -eq 0 -o $# -gt 1 ]; then
 echo "Usage: $0 <problem file>"
 exit 2
fi

if [ ! -r "$1" ]; then
 echo "Error: File $1 not found" >&2
 exit 2
fi

FILE=$1

$PROLOG_PATH $PROLOG_OPTIONS \
  "style_check(-singleton),\
   ['$PROVER'], ['$FILE'], cnf(Name,_,F),\
   ( prove(F) -> R='Theorem' ; R='Non-Theorem'),\
   nl, write('$FILE'), write(' is a '), write(R), nl,\
   halt."

exit 0