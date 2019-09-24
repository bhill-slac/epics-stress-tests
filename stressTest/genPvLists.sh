#!/bin/bash
LAUNCH_SCRIPT=$(basename ${BASH_SOURCE[0]})
SCRIPTDIR=`readlink -f $(dirname ${BASH_SOURCE[0]})`
if [ $# -lt 2 -o "$1" == "-h" -o "$2" == "-h" -o "$1" == "--help" ]; then
	echo Usage: $LAUNCH_SCRIPT testTop clientName
	exit 1
fi
export TEST_TOP=$1
export CLIENT_NAME=$2
TEST_NAME=$(basename $TEST_TOP)


# This part can be replaced w/ python front end
# for each host
#	ssh to host and launch a stressTestMgr.py instance
#
# Start test: date > $STRESSTEST_TOP/$TESTNAME/startTime

# Each stressTestMgr.py instance does the following:
# Monitor startTime files
# if currentTime < startTime + 1 sec
#	Read configuration from env files
#	Generate pvlist if APPTYPE is pvCapture
#	Dump test env variables to log
#	Dump host info to $STRESSTEST_TOP/$TESTNAME/$HOSTNAME/*.info
#   For each client
#		if currentTime > startTime + clientStartDelay
#			launch client pyProcMgr instance
#		if currentTime > startTime + testDuration + clientStopDelay
#			kill client pyProcMgr instance
#	Do periodic timestamped cat of /proc/loadavg into TEST_LOG
#		% cat /proc/loadavg
#		0.01 0.04 0.05 1/811 22246
#		1min 5min 15min numExecuting/numProcessesAndThreads lastPID
#	if currentTime > stopTime
#   	For each client
#			if currentTime > startTime + testDuration + clientStopDelay
#				kill client pyProcMgr instance

#


# Get hostname
HOSTNAME=`hostname -s`

export N_PVS=$(($TEST_N_SERVERS*$TEST_N_COUNTERS))
echo N_PVS=$N_PVS
export N_PVS_PER_CLIENT=$((($N_PVS+$TEST_N_CLIENTS-1)/$TEST_N_CLIENTS))
echo N_PVS_PER_CLIENT=$N_PVS_PER_CLIENT
# Hack
#TEST_N_PVCAPTURE=2
#N_PVS_PER_CLIENT=5

TEST_HOST_DIR=$STRESSTEST_TOP/$TESTNAME/$HOSTNAME
mkdir -p $TEST_HOST_DIR

# Create PV Lists for pvCapture clients
P=0
CLIENT_INSTANCE=${CLIENT_NAME}00
mkdir -p $TEST_DIR/$CLIENT_INSTANCE
cat /dev/null > $TEST_DIR/$CLIENT_INSTANCE/pvs.list
for (( C = 0; C < $TEST_N_CLIENTS ; )) do
	for (( N = 0; N < $TEST_N_COUNTERS ; ++N )) do
		for (( S = 0; S < $TEST_N_SERVERS ; ++S )) do
			if (( C >= $TEST_N_CLIENTS )) ; then
				continue;
			fi
			if (( $S >= 10 )); then
				PRE=${TEST_PV_PREFIX}$S
			else
				PRE=${TEST_PV_PREFIX}0$S
			fi
			if (( $N >= 10 )); then
				PV=${PRE}:Count${N}
			else
				PV=${PRE}:Count0${N}
			fi
			echo $PV >> $TEST_DIR/$CLIENT_INSTANCE/pvs.list
			P=$(($P+1))
			if (( $P >= $N_PVS_PER_CLIENT )) ; then
				# Switch to next client
				P=0
				C=$(($C+1))
				if (( $C >= 10 )); then
					CLIENT_INSTANCE=${CLIENT_NAME}$C
				else
					CLIENT_INSTANCE=${CLIENT_NAME}0$C
				fi
				if (( $C < $TEST_N_CLIENTS )) ; then
					mkdir -p $TEST_DIR/$CLIENT_INSTANCE
					cat /dev/null > $TEST_DIR/$CLIENT_INSTANCE/pvs.list
				fi
			fi
		done
	done
done

