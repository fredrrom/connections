#!/bin/sh
#-----------
# File:      mleancop.sh
# Version:   1.3 (1.3b)
# Date:      1 January 2014
#-----------
# Purpose:   Invokes the MleanCoP prover
# Usage:     ./mleancop.sh [--source-dir <dir>] <problem file> [<time limit>]
# Author:    Jens Otten
# Web:       www.leancop.de/mleancop/
# Copyright: (c) 2007-2014 by Jens Otten
# License:   GNU General Public License
#-----------

#-----------
# Parameters

# set modal logic to D,T,S4,S5 or multimodal [d|t|s4|s5|multi]
LOGIC=s4

# set domain to constant, cumulative or varying [const|cumul|vary]
DOMAIN=cumul

# set MleanCoP prover path
PROVER_PATH=.

# set Prolog system, path, and further options

PROLOG=eclipse
PROLOG_PATH=/usr/bin/eclipse
PROLOG_OPTIONS='-e'

#PROLOG=swi
#PROLOG_PATH=/usr/bin/swipl
#PROLOG_OPTIONS='-g assert((print(A):-write(A)))
#                -nodebug -L120M -G120M -T100M -q -t'

#PROLOG=sicstus
#PROLOG_PATH=/usr/bin/sicstus
#PROLOG_OPTIONS='--nologo --noinfo --goal'

# print proof [yes|no]
PRINT_PROOF=yes
# save proof [yes|no]
SAVE_PROOF=no

# set TPTP library path
# TPTP=.

# explicit source/include path; exported as TPTP for the Prolog translator
SOURCE_DIR=

#----------
# Functions

mleancop()
{
# Input: $SET, $COMP, $TIME_PC
  TLIMIT=`expr $TIME_PC '*' $TIMELIMIT / 111`
  if [ $TLIMIT -eq 0 ]; then TLIMIT=1; fi
  $PROLOG_PATH $PROLOG_OPTIONS \
  "assert(prolog('$PROLOG')),\
   ['$PROVER_PATH/mleancop_main.pl'],\
   asserta(logic('$LOGIC')),\
   asserta(domain('$DOMAIN')),\
   mleancop_main('$FILE',$SET,_),\
   halt."\
   > $OUTPUT &
  PID=$!
  CPU_SEC=0
  trap "rm $OUTPUT; kill $PID >/dev/null 2>&1; exit 2"\
   ALRM XCPU INT QUIT TERM
  while [ $CPU_SEC -lt $TLIMIT ]
  do
    sleep 1
    CPUTIME=`ps -p $PID -o time | grep :`
    if [ ! -n "$CPUTIME" ]; then break; fi
    CPU_H=`expr 1\`echo $CPUTIME | cut -d':' -f1\` - 100`
    CPU_M=`expr 1\`echo $CPUTIME | cut -d':' -f2\` - 100`
    CPU_S=`expr 1\`echo $CPUTIME | cut -d':' -f3\` - 100`
    CPU_SEC=`expr 3600 '*' $CPU_H + 60 '*' $CPU_M + $CPU_S`
  done
  if [ -n "$CPUTIME" ]
  then rm $OUTPUT; kill $PID >/dev/null 2>&1
  else
    RESULT1=`egrep ' Theorem| Unsatisfiable' $OUTPUT`
    RESULT2=`egrep ' Non-Theorem| Satisfiable' $OUTPUT`
    if [ $COMP = n ]; then RESULT2= ; fi
    if [ -n "$RESULT1" -o -n "$RESULT2" ]
    then
      if [ $PRINT_PROOF = yes ]; then cat $OUTPUT
      else if [ -n "$RESULT1" ]; then echo $RESULT1
           else echo $RESULT2; fi
      fi
      if [ $SAVE_PROOF = yes ]; then mv $OUTPUT $PROOF_FILE
      else rm $OUTPUT; fi
      if [ -n "$RESULT1" ]; then exit 0; else exit 1; fi
    else rm $OUTPUT
    fi
  fi
}

#-------------
# Main Program

usage()
{
 echo "Usage: $0 [--source-dir <dir>] <problem file> [<time limit>]"
}

while [ $# -gt 0 ]
do
 case "$1" in
  --source-dir)
   if [ $# -lt 2 ]; then usage; exit 2; fi
   SOURCE_DIR=$2
   shift 2 ;;
  --source-dir=*)
   SOURCE_DIR=${1#*=}
   shift ;;
  --)
   shift
   break ;;
  -*)
   echo "Error: Unknown option $1" >&2
   usage
   exit 2 ;;
  *)
   break ;;
 esac
done

if [ $# -eq 0 -o $# -gt 2 ]; then
 usage
 exit 2
fi

if [ -n "$SOURCE_DIR" ]; then
 if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: Source dir $SOURCE_DIR not found" >&2
  exit 2
 fi
 TPTP=$SOURCE_DIR
 export TPTP
fi

if [ ! -r "$1" ]; then
 echo "Error: File $1 not found" >&2
 exit 2
fi

if [ -n "`echo "$2" | grep '[^0-9]'`" ]; then
 echo "Error: Time $2 is not a number" >&2
 exit 2
fi

if [ $# -eq 1 ]
 then TIMELIMIT=100
 else TIMELIMIT=$2
fi

FILE=$1
PROOF_FILE=$FILE.proof
OUTPUT=TMP_OUTPUT_mleancop_`date +%F_%T_%N`

set +m

# invoke MleanCoP core prover with different settings SET
# for time TIME_PC [%]; COMP=y iff settings are complete

SET="[cut,scut,comp(7)]";      COMP=y; TIME_PC=20; mleancop
SET="[def,cut]";               COMP=n; TIME_PC=20; mleancop
SET="[nodef]";                 COMP=y; TIME_PC=10; mleancop
SET="[reo(23),cut,scut]";      COMP=n; TIME_PC=10; mleancop
SET="[reo(31),cut,scut]";      COMP=n; TIME_PC=10; mleancop
SET="[reo(47),cut,scut]";      COMP=n; TIME_PC=10; mleancop
SET="[reo(25),def,cut,scut]";  COMP=n; TIME_PC=5;  mleancop
SET="[reo(42),conj,cut,scut]"; COMP=n; TIME_PC=5;  mleancop
SET="[conj,def,cut,scut]";     COMP=n; TIME_PC=5;  mleancop
SET="[def]";                   COMP=y; TIME_PC=99; mleancop

echo Timeout
exit 2
