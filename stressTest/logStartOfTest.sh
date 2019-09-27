#!/bin/bash
echo TEST_NAME=$TEST_NAME
if [ "$TEST_APPTYPE" == "loadServer" ]; then
	echo "Launching $TEST_N_CLIENTS ${TEST_APPTYPE} IOCs w/ $TEST_N_COUNTERS Counters and Circular buffers each"
else
	echo "Launching $TEST_N_CLIENTS ${TEST_APPTYPE} clients"
fi
echo TEST_BASEPORT=$TEST_BASEPORT
echo TEST_CIRCBUFF_SIZE=$TEST_CIRCBUFF_SIZE
if [ "$TEST_DRIVE" == "drive" ]; then
echo TEST_DRIVE=$TEST_DRIVE
echo TEST_COUNTER_RATE=$TEST_COUNTER_RATE
echo TEST_COUNTER_DELAY=$TEST_COUNTER_DELAY
elif [ "$TEST_DRIVE" == "ca_drive" ]; then
echo TEST_DRIVE=$TEST_DRIVE
echo TEST_CA_LNK=$TEST_CA_LNK
#else
#echo TEST_DRIVE=$TEST_DRIVE
fi
echo TEST_EPICS_PVA_SERVER_PORT=$TEST_EPICS_PVA_SERVER_PORT
echo TEST_EPICS_PVA_BROADCAST_PORT=$TEST_EPICS_PVA_BROADCAST_PORT
echo TEST_PV_PREFIX=$TEST_PV_PREFIX
#echo N_CNT_PER_SERVER=$N_CNT_PER_SERVER

echo Start: `date`
uname -a > $TEST_HOST_DIR/uname.info
cat /proc/cpuinfo > $TEST_HOST_DIR/cpu.info
cat /proc/meminfo > $TEST_HOST_DIR/mem.info
cat /proc/loadavg > $TEST_HOST_DIR/loadavg.info

