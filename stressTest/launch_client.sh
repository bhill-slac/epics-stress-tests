#!/bin/bash
# TODO: Generate custom launch script for each client via python
# Could replace all this w/ just running generated script remotely via procServ bash daemon.
LAUNCH_SCRIPT=$(basename ${BASH_SOURCE[0]})
SCRIPTDIR=`readlink -f $(dirname ${BASH_SOURCE[0]})`
if [ $# -lt 2 -o "$1" == "-h" -o "$2" == "-h" -o "$1" == "--help" ]; then
	echo Usage: $LAUNCH_SCRIPT testTop clientName
	exit 1
fi
export TEST_TOP=$1
export CLIENT_NAME=$2
echo TEST_TOP=$TEST_TOP
echo CLIENT_NAME=$CLIENT_NAME
TEST_NAME=$(basename $TEST_TOP)
STRESSTEST_TOP=$(dirname $TEST_TOP)
HOST_NAME=`hostname -s`
TEST_HOST_DIR=$TEST_TOP/$HOST_NAME

# Read env files for test
function readIfFound()
{
	if [ -r $1 ]; then
		echo "Reading: ... $1";
		source $1;
	else
		echo "Not Found:   $1";
	fi
}
readIfFound $SCRIPTDIR/stressTestDefault.env
readIfFound $TEST_TOP/../siteDefault.env
readIfFound $TEST_TOP/siteDefault.env
readIfFound $TEST_HOST_DIR/host.env
readIfFound $TEST_TOP/test.env
readIfFound $TEST_TOP/${CLIENT_NAME}.env
readIfFound $SCRIPTDIR/${TEST_APPTYPE}Default.env
# Read client env again so it can override TEST_APPTYPE defaults
readIfFound $TEST_TOP/${CLIENT_NAME}.env

# Make sure env is exported
#source $SCRIPTDIR/exportStressTestEnv.sh

# Setup site specific environment
if [ -f $SCRIPTDIR/site_setup_env.sh ]; then
	source $SCRIPTDIR/site_setup_env.sh 
else
	echo Unable to setup site environment via soft link site_setup_env.sh
	echo Full path: $SCRIPTDIR/site_setup_env.sh 
	exit 1
fi

# See if host has custom site_setup_env.sh
if [ -f $TEST_HOST_DIR/site_setup_env.sh ]; then
	source $TEST_HOST_DIR/site_setup_env.sh;
fi

# Make sure we can find procServ and pyProcMgr.py
PROCSERV=`which procServ`
if [ ! -e "$PROCSERV" ]; then
	echo "Error: procServ not found!"
	exit 1
fi

LOADSERVER=`which loadServer`
if [ ! -e "$LOADSERVER" ]; then
	echo "Error: loadServer not found!"
	exit 1
fi
LOADSERVER_BIN=`dirname $LOADSERVER`
LOADSERVER_TOP=`readlink -f $LOADSERVER_BIN/../..`

PYPROCMGR=`which pyProcMgr.py`
if [ ! -e "$PYPROCMGR" ]; then
	echo "Error: pyProcMgr.py not found!"
	exit 1
fi

PVCAPTURE=`which pvCapture`
if [ ! -e "$PVCAPTURE" ]; then
	echo "Error: pvCapture not found!"
	exit 1
fi

TEST_DIR=$TEST_HOST_DIR/clients
mkdir -p $TEST_DIR

# Make sure env is exported
source $SCRIPTDIR/exportStressTestEnv.sh

# Generate PV list for clients
$SCRIPTDIR/genPvLists.sh $TEST_TOP $CLIENT_NAME

# Log start of test
TEST_LOG=$TEST_DIR/${CLIENT_NAME}.log
echo TEST_LOG=$TEST_LOG
export TEST_DIR TEST_HOST_DIR
$SCRIPTDIR/logStartOfTest.sh | tee $TEST_LOG

echo CLIENT_CMD=$CLIENT_CMD
if [ "$CLIENT_CMD" == "" ]; then
	echo "Error: CLIENT_CMD not defined!"
	exit 1
fi

KILLER=$TEST_DIR/${CLIENT_NAME}.kill
echo KILLER=$KILLER

# Run test on host
echo $PYPROCMGR -v -c $TEST_N_CLIENTS -n $CLIENT_NAME \
	-p $TEST_BASEPORT -d $TEST_DELAY_PER_CLIENT -D $TEST_DIR \
	-k $KILLER \
	"$CLIENT_CMD" | tee $TEST_LOG;
$PYPROCMGR -v -c $TEST_N_CLIENTS -n $CLIENT_NAME \
	-p $TEST_BASEPORT -d $TEST_DELAY_PER_CLIENT -D $TEST_DIR \
	-k $KILLER \
	"$CLIENT_CMD"; \
echo Done: `date` | tee -a $TEST_LOG
