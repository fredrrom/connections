#!/bin/sh
#-----------
# File:      leancop_trans.sh
# Version:   2.2
# Date:      11 February 2021
#-----------
# Purpose:   Invokes the leanCoP clause translation (add eq-axioms)
# Usage:     ./leancop_trans.sh <problem file> [<output file>]
# Author:    Jens Otten
# Web:       www.leancop.de
# Copyright: (c) 2007-2021 by Jens Otten
# License:   GNU General Public License
#-----------

#-----------
# Parameters

# set leanCoP prover path
PROVER_PATH=.

# set Prolog system, path, and options

PROLOG=eclipse
#PROLOG_PATH=$HOME/Software/eclipse_5.10/eclipse
PROLOG_PATH=/usr/bin/eclipse
PROLOG_OPTIONS='-e'

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# DOES NOT RUN WITH SWI PROLOG (exists predicate in leancop_tptp2!)
#
#PROLOG=swi
#PROLOG_PATH=/usr/bin/swipl
#PROLOG_OPTIONS='-g assert((print(A):-write(A)))
#                -nodebug -L120M -G120M -T100M -q -g'

#PROLOG=sicstus
#PROLOG_PATH=/usr/bin/sicstus
#PROLOG_OPTIONS='--nologo --noinfo --goal'

# set TPTP library path
# TPTP=.

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

