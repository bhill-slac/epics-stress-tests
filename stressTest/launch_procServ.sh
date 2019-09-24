#!/bin/bash
LAUNCH_SCRIPT=$(basename ${BASH_SOURCE[0]})
SCRIPTDIR=`readlink -f $(dirname ${BASH_SOURCE[0]})`
if [ $# -lt 1 -o "$1" == "-h" -o "$1" == "--help" ]; then
	echo Usage: $LAUNCH_SCRIPT procServPort
	exit 1
fi
PROCSERV_PORT=$1

# Setup site specific environment
if [ -f $SCRIPTDIR/site_setup_env.sh ]; then
	source $SCRIPTDIR/site_setup_env.sh 
else
	echo Unable to setup site environment via soft link site_setup_env.sh
	echo Full path: $SCRIPTDIR/site_setup_env.sh 
	exit 1
fi

# Make sure we can find procServ and pyProcMgr.py
PROCSERV=`which procServ`
if [ ! -e "$PROCSERV" ]; then
	echo "Error: procServ not found!"
	exit 1
fi

PROCSERV_ARGS="-f --allow --ignore '^D' --name procServStressTest --noautorestart --coresize 0 "

$PROCSERV $PROCSERV_ARGS $PROCSERV_PORT /bin/sh --noediting -i
