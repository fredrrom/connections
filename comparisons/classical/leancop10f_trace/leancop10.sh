#!/bin/sh
#-----------
# File:      leancop10.sh
# Version:   1.0
# Date:      5 Dec 2021
#-----------
# Purpose:   Invokes the leanCoP prover
# Usage:     ./leancop10.sh <problem file>
# Author:    Jens Otten
# Web:       www.leancop.de
# Copyright: (c) 2022 by Jens Otten
# License:   GNU General Public License
#-----------

#-----------
# Parameters

# set the leanCoP prover path
PROVER_PATH=leancop10f_trace

# set Prolog system (ECLiPSe 5.x or SWI), path and options

#PROLOG=eclipse
#PROLOG_PATH=/usr/bin/eclipse
#PROLOG_OPTIONS='-e'

PROLOG=swi
PROLOG_PATH=swipl
PROLOG_OPTIONS='--debug=false -O -q -g'
#PROLOG_OPTIONS='-nodebug -O -L120M -G120M -T100M -q -g'

# set TPTP library path
export TPTP=../../../conjectures/TPTP-v6.4.0

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
set +m

# invoke leanCoP core prover with settings SET

SET="[]"

#$PROLOG_PATH $PROLOG_OPTIONS

$PROLOG_PATH $PROLOG_OPTIONS \
  "assert(prolog('$PROLOG')),\
   ['$PROVER_PATH/leancop10_main.pl'],\
   leancop10_main('$FILE',$SET,_),\
   halt."\

exit 0

