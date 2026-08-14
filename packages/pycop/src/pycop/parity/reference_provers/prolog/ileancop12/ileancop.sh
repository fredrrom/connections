#!/bin/sh
#-------------
# File:    ileancop.sh
# Version: 1.2
# Date:    1 July 2007
#-------------
# Purpose: Invokes the ileanCoP core theorem prover
# Usage:   ./ileancop.sh <problem file> [<time limit>]
# Author:  Jens Otten
# Web:     www.leancop.de/ileancop/
#-------------

#-----------
# Parameters

# set ECLiPSe Prolog path
ECLIPSE=/usr/local/bin/eclipse

# set ileanCoP prover path
PROVERPATH=/home/jeotten/Provers/ileancop12

#----------
# Functions

ileancop()
{
 # Input: $SETTINGS, $TLIMIT ; Output: $RETURN
 "$ECLIPSE" -b "$PROVERPATH/leancop_tlimit.pl" \
  -e "leancop_tlimit('$PROVERPATH/ileancop12',$SETTINGS,'$FILE',$TLIMIT)"
 RETURN=$?
 if [ $RETURN -eq 0 ]; then echo " $FILE is an Intuitionistic Theorem"; exit 0; fi
}

#-------------
# Main Program

if [ $# -eq 0 -o $# -gt 2 ]; then
 echo "Usage: $0 <problem file> [<time limit>]" >&2
 exit 2
fi

if [ ! -r "$1" ]; then
 echo "Error: File $1 not found"
 exit 2
fi

case "$2" in (*[!0-9]*)
 echo "Error: Time $2 is not a number"
 exit 2 ;;
esac

FILE=$1

if [ $# -eq 1 ]
 then TIMELIMIT=300
 else TIMELIMIT=$2
fi

# invoke the core prover with different settings

SETTINGS="[def,scut,cut,comp(7)]"; TLIMIT=$(( 1 * $TIMELIMIT / 50)); ileancop
if [ $RETURN -eq 1 ]; then echo "$FILE is an Intuitionistic Non-Theorem"; exit 1; fi
SETTINGS="[def,scut,cut]";  TLIMIT=$((30 * $TIMELIMIT / 50)); ileancop
SETTINGS="[conj,scut,cut]"; TLIMIT=$((10 * $TIMELIMIT / 50)); ileancop
SETTINGS="[def,conj,cut]";  TLIMIT=$(( 5 * $TIMELIMIT / 50)); ileancop
SETTINGS="[def]";           TLIMIT=$TIMELIMIT               ; ileancop
if [ $RETURN -eq 1 ]; then echo "$FILE is an Intuitionistic Non-Theorem"; exit 1; fi
exit 2
