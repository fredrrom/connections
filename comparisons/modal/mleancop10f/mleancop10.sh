#!/bin/sh
#-----------
# File:      mleancop10.sh
# Version:   1.0
# Date:      12 Dec 2022
#-----------
# Purpose:   Invokes the MleanCoP prover
# Usage:     ./mleancop10.sh <problem file>
# Author:    Jens Otten
# Web:       www.leancop.de/mleancop/
# Copyright: (c) 2022 by Jens Otten
# License:   GNU General Public License
#-----------

#-----------
# Parameters

# set modal logic to D,T,S4 or S5 [d|t|s4|s5|multi]
LOGIC=s4
# set domain to constant,cumulative or varying [const|cumul|vary]
DOMAIN=cumul

# set the MleanCoP prover path
PROVER_PATH=mleancop10f

# set Prolog system (ECLiPSe 5.x or SWI), path and options

#PROLOG=eclipse
#PROLOG_PATH=/usr/bin/eclipse
#PROLOG_OPTIONS='-e'

PROLOG=swi
PROLOG_PATH=swipl
PROLOG_OPTIONS='--debug=false -O -q -g'
#PROLOG_OPTIONS='-nodebug -O -L120M -G120M -T100M -q -g'

# set TPTP library path
export TPTP=../../../conjectures/QMLTP-v1.1

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

# invoke MleanCoP core prover with settings SET

SET="[]"

#$PROLOG_PATH $PROLOG_OPTIONS

$PROLOG_PATH $PROLOG_OPTIONS \
  "assert(prolog('$PROLOG')),\
   ['$PROVER_PATH/mleancop10_main.pl'],\
   asserta(logic('$LOGIC')),\
   asserta(domain('$DOMAIN')),\
   mleancop10_main('$FILE',$SET,_),\
   halt."\

exit 0

