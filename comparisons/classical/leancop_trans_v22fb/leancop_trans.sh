#!/bin/sh
#-----------
# File:      leancop_trans.sh
# Version:   2.2f
# Date:      5 December 2022
#-----------
# Purpose:   Invokes the leanCoP clause translation (add eq-axioms)
# Usage:     ./leancop_trans.sh <problem file> [<output file>]
# Author:    Jens Otten
# Web:       www.leancop.de
# Copyright: (c) 2007-2022 by Jens Otten
# License:   GNU General Public License
#-----------

#-----------
# Parameters

# set leanCoP prover path
PROVER_PATH=leancop_trans_v22fb

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

#----------
# Functions

leancop_tr()
{
# Input: $SET
  $PROLOG_PATH $PROLOG_OPTIONS \
  "assert(prolog('$PROLOG')),\
   ['$PROVER_PATH/leancop_main_trans.pl'],\
   leancop_main_trans('$FILE',$SET,_,'$FILE2'),\
   halt."
}

#-------------
# Main Program

if [ $# -eq 0 -o $# -gt 2 ]; then
 echo "Usage: $0 <problem file> [<output file>]"
 exit 2
fi

if [ ! -r "$1" ]; then
 echo "Error: File $1 not found" >&2
 exit 2
fi

FILE=$1

if [ $# -eq 2 ]
 then FILE2=$2
 else FILE2=$1.cnf
fi

set +m

# invoke leanCoP core prover with different settings SET

SET="[]"; leancop_tr

