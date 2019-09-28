#!/bin/bash

if [ $# -lt 2 ]; then
	echo "Usage: ${BASH_SOURCE[0]} testDir PV1 ..."
	exit
fi
TEST_DIR=$1
shift
PVS=$*
echo TEST_DIR=$TEST_DIR
echo PVS=$PVS

PVGET_EXE=`which pvget`
if [ ! -e "$PVGET_EXE" ]; then
	echo "Error: pvget not found!"
	exit 1
fi

if [ -z "$TEST_PROVIDER" ]; then
	TEST_PROVIDER=pva
fi
if [ -z "$TEST_PVGET_TIMEOUT" ]; then
	TEST_PVGET_TIMEOUT=1
fi
if [ -z "$TEST_PVGET_REPEAT" ]; then
	TEST_PVGET_REPEAT=1
fi

NSAM=`caget -t -w 1 ${PVS[0]}.NSAM`
if $? ; then
	NSAM=1
endif
export PV_SIZE=$(($NSAM * 8))
echo PV_SIZE=$PV_SIZE

mkdir -p $TEST_DIR
while (( 1 ));
do
	#echo "Checking for active pvget jobs:"
	#ps u -C pvget

	for PV in $PVS;
	do
		echo Get: `date` >> $TEST_DIR/$PV.pvgetarray
		pvget -p $TEST_PROVIDER -w $TEST_PVGET_TIMEOUT $PV > /dev/null; \
		echo Read $PV_SIZE bytes: `date` >> $TEST_DIR/$PV.pvgetarray &
	done
	wait
	#echo "pvgetarray jobs done"
	sleep $TEST_PVGET_REPEAT
done

