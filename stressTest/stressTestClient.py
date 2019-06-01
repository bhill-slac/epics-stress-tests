#!/usr/bin/env python3
import os
import json
from stressTestPV import *

class InvalidStressTestCaptureFile( Exception ):
    pass

class InvalidStressTestPathError( Exception ):
    pass

def pathToTestAttr( filePath ):
    '''Stress test directory hierarchy is expected to follow this pattern.
    TESTNAME/HOSTNAME/clients/CLIENTNAME/PVNAME.*
    TESTNAME/HOSTNAME/clients/CLIENTNAME/CLIENTNAME.log
    TESTNAME/HOSTNAME/servers/SERVERNAME/PVNAME.*
    TESTNAME/HOSTNAME/servers/SERVERNAME/SERVERNAME.log
    Returns:
        ( TESTNAME, HOSTNAME, "client", CLIENTNAME, PVNAME )
        ( TESTNAME, HOSTNAME, "client", CLIENTNAME, None   )
        ( TESTNAME, HOSTNAME, "server", SERVERNAME, PVNAME )
        ( TESTNAME, HOSTNAME, "server", SERVERNAME, None   )
        or
         raise InvalidStressTestPathError
    '''
    try:
        ( tempPath, fileName ) = os.path.split( filePath )
        ( tempPath, appName  ) = os.path.split( tempPath )
        ( tempPath, appType  ) = os.path.split( tempPath )
        ( tempPath, hostName ) = os.path.split( tempPath )
        ( tempPath, testName ) = os.path.split( tempPath )
        if testName == '':
            raise InvalidStressTestPathError( "Invalid TEST/HOST/TYPE/APPNAME/FILENAME path: %s" % filePath )

        pvName = None
        root = fileName.split('.')[0]
        if appName != root:
            pvName = root
        if appType == "servers":
            return ( testName, hostName, "server", appName, pvName )
        if appType == "clients":
            return ( testName, hostName, "client", appName, pvName )
        raise InvalidStressTestPathError( "Invalid TEST/HOST/TYPE/APPNAME/FILENAME TYPE: %s" % filePath )
    except BaseException as e:
        raise InvalidStressTestPathError( str(e) )

def readPVCaptureFile( filePath ):
    '''Capture files should follow json syntax and contain
    a list of tsPV values.
    Each tsPV is a list of timestamp, value.
    Each timestamp is a list of EPICS secPastEpoch, nsec.
    Ex.
    [
        [ [ 1559217327, 738206558], 8349 ],
        [ [ 1559217327, 744054279], 8350 ]
    ]
    '''
    try:
        f = open( filePath )
        contents = json.load( f )
        return contents
    except BaseException as e:
        raise InvalidStressTestCaptureFile( "readPVCaptureFile Error: %s: %s" % ( filePath, e ) )

class stressTestClient:
    def __init__( self, clientName, hostName ):
        self._clientName  = clientName
        self._hostName    = hostName
        self._testPVs     = {}		# Dict of stressTestPV instances, keys are pvName strings
        self._tsNumPVs    = {}		# Dict of active PV counts, keys are int secPastEpoch values
        self._tsRates     = {}		# Dict of cumulative PV collection rate for all client testPVs
        self._tsMissRates = {}		# Dict of cumulative miss rate for all client testPVs
        self._numMissed   = 0		# Number of cumulative missed counts for all client testPVs
        self._numTsValues = 0		# Number of timestamped values collected for all client testPVs
        self._startTime   = None	# Earliest timestamp of all client testPVs
        self._endTime     = None	# Latest timestamp of all client testPVs

    # Accessors
    def getHostName( self ):
        return self._hostName
    def getName( self ):
        return self._clientName
    def getNumPVs( self ):
        return len(self._testPVs)
    def getTestPVs( self ):
        return self._testPVs
    def getNumMissed( self ):
        return self._numMissed
    def getNumTsValues( self ):
        numTsValues = 0  # Could compute this during analysis and cache
        for pvName in self._testPVs:
            testPV = self._testPVs[pvName]
            numTsValues += testPV.getNumTsValues()
        return numTsValues
    def getEndTime( self ):
        return self._endTime
    def getStartTime( self ):
        return self._startTime
    def getTsRates( self ):
        return self._tsRates
    def getTsMissRates( self ):
        return self._tsMissRates
    def getTestPVs( self ):
        return self._testPVs

    def getTestPV( self, pvName ):
        testPV = None
        if pvName in self._testPVs:
            testPV = self._testPVs[pvName]
        if testPV is None:
            testPV = stressTestPV( pvName )
            print( "getTestPV: Created new testPV %s" % testPV.getName() )
            self._testPVs[pvName] = testPV
        return testPV

    # stressTestClient.addTsValues
    def addTsValues( self, pvName, tsValues ):
        testPV = self.getTestPV( pvName )
        if testPV is not None:
            testPV.addTsValues( tsValues )

    # stressTestClient.analyze
    def analyze( self ):
        self._totalNumTsValues = self.getNumTsValues()
        self._tsMissRates = { }
        self._numMissed = 0
        self._endTime   = None
        self._startTime = None
        for pvName in self._testPVs:
            testPV = self._testPVs[pvName]
            testPV.analyze()
            self._numMissed += testPV.getNumMissed()
            if  self._startTime is None or self._startTime > testPV.getStartTime():
                self._startTime = testPV.getStartTime()
            if  self._endTime is None or self._endTime < testPV.getEndTime():
                self._endTime = testPV.getEndTime()

            # Compute client count rates
            pvTsRates = testPV.getTsRates()
            for sec in pvTsRates:
                # Initialize client dict for each sec
                if sec not in self._tsRates:
                    self._tsRates[sec] = 0
                if sec not in self._tsNumPVs:
                    self._tsNumPVs[sec] = 0
                # Add contributions for this PV
                self._tsRates[sec]  += pvTsRates[sec]
                self._tsNumPVs[sec] += 1

            # Compute client missed count rates
            pvTsMissRates = testPV.getTsMissRates()
            for sec in pvTsMissRates:
                if sec not in self._tsMissRates:
                    self._tsMissRates[sec] = 0
                missRate = pvTsMissRates[sec]
                self._tsMissRates[sec] += missRate

