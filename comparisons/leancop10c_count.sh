#!/bin/sh
#-----------
# leancop10b.sh, v1.0bc (30 Apr 2021)
#-----------
# Purpose:  Invokes leanCoP 1.0
# Usage:    ./leancop10c_count.sh <problem file>
#-----------

#-----------
# Parameters

PROVER=leancop10c_swi_count.pl

PROLOG_PATH=swipl
PROLOG_OPTIONS='-g'

#-------------
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

