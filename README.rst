===============================
epics-stress-tests
===============================

.. image:: https://img.shields.io/travis/slac-epics/epics-stress-tests.svg
        :target: https://travis-ci.org/slac-epics/epics-stress-tests

.. image:: https://img.shields.io/pypi/v/epics-stress-tests.svg
        :target: https://pypi.python.org/pypi/epics-stress-tests


Python scripts for distributed client/server EPICS CA and PVA network stress tests.

Documentation
-------------

Sphinx-generated documentation for this project can be found here:
https://slac-epics.github.io/epics-stress-tests/


Requirements
------------

Describe the project requirements (i.e. Python version, packages and how to install them)

Installation
------------

Describe the installation procedure

Running the Tests
-----------------
::

  $ python run_tests.py
   
Directory Structure
-------------------

This repo is based the PCDS python cookiecutter. See the following github page for more info:

- `cookiecutter-pcds-python <https://github.com/pcdshub/cookiecutter-pcds-python>`_

**EPICS stress tests for CA and PVA network protocols**

Python scripts read test configuration files which describe which test servers
and clients to run on which hosts and the timing for when each server and/or client runs.

Uses some new executables from stressTestClients project to facilitate capture and post analysis of
EPICS PV's via Channel Access (CA) and PVAccess (PVA) network protocols.

* pvGet - Derived from pvget but adds options to capture, repeat, save, etc.   Used to test success of repeated cycles of connect, fetch data, and disconnect.
* pvCapture - Derived from pvmonitor but adds options to capture, save, PV list from file, etc.   Used to test PVAccess monitor connections.

The .env files are bash compatible shell scripts that set bash environment variables.
They are also read by some of the python test management code.

The .cfg files are json format dictionaries with test configuration.

**Test Folder Organization**
---------------------------

Test output is organized as follows:
GW\_TESTS=/reg/d/iocData/gwTest
TEST\_NAME=YourTestName
$TEST\_TOP=$GW\_TESTS/$TEST\_NAME

**Test Configuration**
---------------------------
$TEST\_TOP/test.cfg               json format dictionary w/ configuration settings for this test

**Test Environment**
---------------------------
Environment files are simple VARIABLE=Value environment variable definitions.
Value can contain other simple environment variable references.
Examples w/ A,B,C variants indicate user can supply 0 or more w/ arbitrary names.

For example:
	APP\_TYPE=pvCapture
	CLIENT\_NAME=${APP\_TYPE}SinglePv
	LOG_FILE=${TEST_TOP}/${HOSTNAME}/${CLIENT_NAME}/${CLIENT_NAME}.log

Order in which test environment files are read:
$TEST\_TOP/test.env                                          Env settings for this test
$TEST\_TOP/loadServer*A*.env                                 loadServerA env settings
$TEST\_TOP/loadServer*B*.env                                 loadServerB env settings
$TEST\_TOP/loadServer*C*.env                                 loadServerC env settings
...
$TEST\_TOP/client*A*.env                                     clientA env settings
$TEST\_TOP/client*B*.env                                     clientB env settings
$TEST\_TOP/client*C*.env                                     clientC env settings
...
$TEST\_TOP/launch\_client*A*.sh                              clientA launch script
$TEST\_TOP/launch\_client*B*.sh                              clientB launch script
$TEST\_TOP/launch\_client*C*.sh                              clientC launch script
...
$TEST\_TOP/*hostname*/cpu.info                               Host CPU Info
$TEST\_TOP/*hostname*/mem.info                               Host Memory Info
$TEST\_TOP/*hostname*/uname.info                             Host OS Info
$TEST\_TOP/*hostname*/clients/client*A*00                    Directory for clientA00 files
$TEST\_TOP/*hostname*/clients/client*A*01                    Directory for clientA01 files
...
$TEST\_TOP/*hostname*/clients/client*A*00/pvs.list           clientA00 PV list
$TEST\_TOP/*hostname*/clients/client*A*00/client*A*00.log    clientA00 console output
$TEST\_TOP/*hostname*/clients/client*A*00/*pvName*.pvget     clientA00 PV data from run\_pvget.sh
$TEST\_TOP/*hostname*/clients/client*A*00/*pvName*.pvGet     clientA00 PV data from pvGet
$TEST\_TOP/*hostname*/clients/client*A*00/*pvName*.pvCapture clientA00 PV data from pvCapture

**Configuration env variables**
--------------------

SCRIPTDIR           path to StressTestClients-git TOP

# Set in client env files (i.e. $TEST\_TOP/clientFoo.env for clientFoo)
APPTYPE             Test type: loadServer, pvCapture, pvGet, run\_pvget, run\_pvgetarray
* loadServer:               Runs a loadServer EPICS IOC (See below for loadServer github URL)
* pvCapture:                Runs a stressTest pvCapture app
* pvGet:                    Runs a stressTest pvGet app
* run\_pvget:                Runs stressTest script run\_pvget.sh that captures output of EPICS pvget. (deprecated)
* run\_pvgetarray:           Runs stressTest script run\_pvgetarray.sh.  Dumps output of pvget but logs timestamp and number elements read.

# Set in $SCRIPTDIR/loadServerDefault.env
STRESSTEST\_TOP                  path to Top Dir For Set Of Stress Tests
TEST\_N\_COUNTERS                 Number of incrementing counters in loadServer apps
TEST\_CIRCBUFF\_SIZE              Size of circular buffers in loadServer apps
TEST\_EPICS\_PVA\_SERVER\_PORT      EPICS\_PVA\_SERVER\_PORT for client apps. Defaults to $EPICS\_PVA\_SERVER\_PORT
TEST\_EPICS\_PVA\_BROADCAST\_PORT   EPICS\_PVA\_BROADCAST\_PORT for client apps. Defaults to $EPICS\_PVA\_BROADCAST\_PORT
TEST\_PV\_PREFIX                  Default prefix for loadServer PVs (See below for loadServer PV naming scheme)

# TODO: Consolidate these by splitting into ${APPTYPE}Default.env files
TEST\_LOADSERVER\_BASEPORT        Base port number for loadServer procServ instances
TEST\_PVCAPTURE\_BASEPORT         Base port number for pvCapture procServ instances
TEST\_PVGET\_BASEPORT             Base port number for pvGet procServ instances
TEST\_RUN\_PVGET\_BASEPORT         Base port number for run\_pvget procServ instances
TEST\_RUN\_PVGETARRAY\_BASEPORT    Base port number for run\_pvgetarray procServ instances
TEST\_RUN\_PVGET\_GW\_BASEPORT      Base port number for run\_pvget\_gw procServ instances
TEST\_N\_LOADSERVERS              Number of loadServer instances to create
TEST\_N\_PVCAPTURE                Number of pvCapture instances to create
TEST\_N\_PVGET                    Number of pvGet instances to create
TEST\_N\_RUN\_PVGET\_CLIENTS        Number of loadServer instances to create
TEST\_N\_RUN\_PVGETARRAY\_CLIENTS   Number of loadServer instances to create

# Set in $SCRIPTDIR/loadServerDefault.env
TEST\_CIRCBUFF\_SIZE=1
TEST\_COUNTER\_RATE=100
TEST\_COUNTER\_DELAY=0.01
TEST\_COUNTER\_DELAY=$(gawk "BEGIN { print 1.0/$TEST\_COUNTER\_RATE }")
TEST\_DRIVE=drive
TEST\_CA\_LNK=Unused

# Used as convenience variable in some scripts 
TEST\_TOP                path to Top Dir for a specfic StressTest instance

**Configuration files**
--------------------

SCRIPTDIR=path to StressTestClientsTOP
$SCRIPTDIR/stressTestDefault.env
$SCRIPTDIR/loadServerDefault.env
# TODO: More ${APPTYPE}Default.env files
# $SCRIPTDIR/pvCaptureDefault.env
