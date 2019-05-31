#!/usr/bin/env python3
import argparse
import textwrap
import os
import sys
import json
import numpy
from stressTestClient import *
#import matplotlib.pyplot as matplot

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

class stressTestPV:
    def __init__( self, pvName ):
        self._pvName = pvName
        self._tsValues = {}
        self._tsRates = {}
        self._tsMissRates = {}

    def getName( self ):
        return self._pvName

    def getNumTsValues( self ):
        return len(self._tsValues)

    def getTsValues( self ):
        return self._tsValues

    def getTsRates( self ):
        return self._tsRates

    def getTsMissRates( self ):
        return self._tsMissRates

    def addTsValues( self, tsValues ):
        # TODO: check for more than one value for the same timestamp
        # TODO: check for out of order timestamps
        self._tsValues.update( tsValues )

    # stressTestPV.analyze
    def analyze( self ):
        ( priorSec, priorValue ) = ( None, None )
        ( missed, count ) = ( 0, 0 )
        for timestamp in self._tsValues:
            sec = int(timestamp)
            if sec != priorSec:
                if priorSec is not None:
                    self._tsRates[priorSec] = count
                    self._tsMissRates[priorSec] = missed
                    ( missed, count ) = ( 0, 0 )
                    missed = 0
                    count = 0
                    priorSec = sec
            count = count + 1
            value = self._tsValues[timestamp]
            if priorValue is not None:
                if priorValue + 1 != value:
                    missed = missed + 1
        self._tsRates[sec] = count
        self._tsMissRates[sec] = missed

class stressTestClient:
    def __init__( self, clientName, hostName ):
        self._clientName = clientName
        self._hostName   = hostName
        self._tsValues = {}
        self._tsRates = {}
        self._tsMissRates = {}
        self._numMissed = 0

    def getHostName( self ):
        return self._hostName

    def getName( self ):
        return self._clientName

    def getNumPVs( self ):
        return len(self._testPVs)

    def getNumMissed( self ):
        return self._numMissed

    def getNumTsValues( self ):
        numTsValues = 0
        for pvName in self._testPVs:
            testPV = self._testPVs[pvName]
            numTsValues = numTsValues + testPV.getNumTsValues()
        return numTsValues

    def getTsRates( self ):
        return self._tsRates

    def getTsMissRates( self ):
        return self._tsMissRates

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
        for pvName in self._testPVs:
            testPV = self._testPVs[pvName]
            testPV.analyze()

            # Compute client count rates
            pvTsRates = testPV.getTsRates()
            for sec in pvTsRates:
                rate = pvTsRates[sec]
                if sec in self._tsRates:
                    self._tsRates[sec] = self._tsRates[sec] + rate

            # Compute client missed count rates
            self._numMissed = 0
            pvTsMissRates = testPV.getTsMissRates()
            for sec in pvTsMissRates:
                missRate = pvTsMissRates[sec]
                self._numMissed = self._numMissed + missRate
                if sec in self._tsMissRates:
                    self._tsMissRates[sec] = self._tsMissRates[sec] + missRate

class stressTest:
    def __init__( self, testName, testPathTop ):
        self._testName = testName
        self._testPath = testPathTop
        self._testClients = {}
        self._testServers = {}
        self._testPVs = {}
        self._gwStats = {}
        self._totalNumPVs = 0
        self._totalNumTsValues = 0

    def analyze( self ):
        print( "stressTestView.analyze: %s ..." % self._testName )
        totalNumPVs = 0
        totalNumTsValues = 0
        for clientName in self._testClients:
            client = self._testClients[clientName]
            client.analyze()

    def report( self ):
        print( "\nStressTest Report:" )
        print( "TestName: %s" % self._testName )
        totalNumPVs = 0
        totalNumTsValues = 0
        totalNumMissed   = 0
        if len(self._testClients):
            print( "Clients:                 NumPVs NumTsValues NumMissed" );
            #      "    CCCCCCCCCCCCCCCCCCCC NNNNNN TTTTTTTTTTT MMMMMMMMM" );
        for clientName in self._testClients:
            client = self._testClients[clientName]
            numPVs           = client.getNumPVs()
            numTsValues      = client.getNumTsValues()
            numMissed        = client.getNumMissed()
            #tsRates          = client.getTsRates()
            #tsMissRates      = client.getTsMissRates()
            totalNumPVs      = totalNumPVs + numPVs
            totalNumTsValues = totalNumTsValues + numTsValues
            totalNumMissed   = totalNumMissed + numMissed
            print( "    %20s %6u %11u %9u" % ( clientName, numPVs, numTsValues, numMissed ) )
        print( "    %20s %6u %11u %9u" % ( "Total", totalNumPVs, totalNumTsValues, totalNumMissed ) )

    def getClient( self, clientName, hostName ):
        clientPath = os.path.join( self._testPath, hostName, "clients", clientName )
        if not os.path.isdir( clientPath ):
            raise InvalidStressTestPathError( "Invalid TEST/HOST/TYPE/APPNAME/FILENAME clientPath: %s" % clientPath )
        client = None
        if clientName in self._testClients:
            client = self._testClients[clientName]
            if client.getHostName() != hostName:
                raise Exception( "stressTest.getClient Error: Client %s host is %s, not %s!" %
                                ( clientName, client.getHostName(), hostName ) )
        if client is None:
            client = stressTestClient( clientName, hostName )
            self._testClients[clientName] = client
        return client

    def processPVCaptureFile( self, filePath ):
        try:
            ( testName, hostName, appType, appName, pvName ) =  pathToTestAttr( filePath )
            tsValueList = readPVCaptureFile( filePath )
            tsValues = {}
            for tsValue in tsValueList:
                timeStamp = tsValue[0]	# timeStamp should be [ secPastEpoch, nsec ]
                value = tsValue[1]
                tsValues[ timeStamp[0] + timeStamp[1]*1e-9 ] = value
            if appType == "client":
                client = self.getClient( appName, hostName )
                client.addTsValues( pvName, tsValues )

        except InvalidStressTestCaptureFile as e:
            print( e )
            pass
        except BaseException as e:
            print( "processPVCaptureFile Error: %s: %s" % ( filePath, e ) )
            pass

    def readFiles( self, dirTop, verbose = True ):
        if not os.path.isdir( dirTop ):
            print( "%s is not a directory!" % dirTop )
        for dirPath, dirs, files in os.walk( dirTop, topdown=True ):
            if verbose:
                (appPath, appName) = os.path.split( dirPath )
                if os.path.split(appPath)[1] == "clients":
                    print( "Processing client %s ..." % appName )
            for fileName in files:
                filePath = os.path.join( dirPath, fileName )
                if fileName.endswith( '.pvget' ):
                    # readPVGetClientFile( fileName )
                    continue
                if fileName.endswith( '.log' ):
                    # readLogFile( fileName )
                    continue
                if fileName.endswith( '.list' ):
                    continue
                if fileName.endswith( '.cfg' ):
                    continue
                if fileName.endswith( '.info' ):
                    # readInfoFile( fileName )
                    continue
                if fileName.endswith( 'pvCapture' ):
                    self.processPVCaptureFile( filePath )
                    continue
        return

def process_options(argv):
    if argv is None:
        argv = sys.argv[1:]
    description =	'stressTestView supports viewing results from CA or PVA network stress tests.\n'
    epilog_fmt  =	'\nExamples:\n' \
                    'stressTestView PATH/TO/TEST/TOP"\n'
    epilog = textwrap.dedent( epilog_fmt )
    parser = argparse.ArgumentParser( description=description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog )
    #parser.add_argument( 'cmd',  help='Command to launch.  Should be an executable file.' )
    #parser.add_argument( 'arg', nargs='*', help='Arguments for command line. Enclose options in quotes.' )
    #parser.add_argument( '-c', '--count',  action="store", type=int, default=1, help='Number of processes to launch.' )
    #parser.add_argument( '-d', '--delay',  action="store", type=float, default=0.0, help='Delay between process launch.' )
    parser.add_argument( '-t', '--top',  action="store", help='Top directory of test results.' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )
    #parser.add_argument( '-p', '--port',  action="store", type=int, default=40000, help='Base port number, procServ port is port + str(procNumber)' )
    #parser.add_argument( '-n', '--name',  action="store", default="pyProc_", help='process basename, name is basename + str(procNumber)' )
    #parser.add_argument( '-D', '--logDir',  action="store", default=None, help='log file directory.' )

    options = parser.parse_args( )

    return options 

def main(argv=None):
    global procList
    options = process_options(argv)

    if options.top:
        if not os.path.isdir( options.top ):
            print( "%s is not a directory!" % options.top )
            return 1
        testName = os.path.split( options.top )[1]
        test1 = stressTest( testName, options.top )
        test1.readFiles( options.top )
        test1.analyze()
        test1.report()

    #if options.verbose:
    #	print( "Full Cmd: %s %s" % ( options.cmd, args ) )
    #	print( "logDir=%s" % options.logDir )

def readCaptureFile( filePath ):
    print( "Done:" )
    return 0

if __name__ == '__main__':
    status = 0
    status = main()
    #try:
    #	status = main()
    #except BaseException as e:
    #	print( "Caught exception during main!" )
    #	print( e )

    # Pre-exit cleanup
    #killProcesses()

    sys.exit(status)
