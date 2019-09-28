#!/usr/bin/env python
#	Name: testManager.py
#	Abstract:
#	A python tool to launch and manage EPICS CA and PVA stress tests
#	Uses threading and paramiko ssh transport to run needed clients and servers on
#	each host machine which will be used in the test. 
#
#	Example:
#		stressTest/testManager.py --testDir /path/to/test/top --testName yourTestName
#
#	Requested features to be added:
#
#==============================================================
from __future__ import print_function
import argparse
import concurrent.futures
import io
import datetime
import glob
import locale
import os
import re
import pprint
#import paramiko
#import procServUtils
import signal
import socket
import string
import subprocess
import sys
import tempfile
import textwrap
import threading
import time

procList = []
activeTests = []
testFutures = {}
testExecutor = None
testDir = None

def makePrintable( rawOutput ):
    if isinstance( rawOutput, str ) and rawOutput.startswith( "b'" ):
        rawOutput = eval(rawOutput)
    if isinstance( rawOutput, bytes ):
        rawOutput = rawOutput.decode()
    if isinstance( rawOutput, list ):
        filtered = []
        for line in rawOutput:
            filtered.append( makePrintable( line ) )
        return filtered
    if not isinstance( rawOutput, str ):
        return str(rawOutput)
    # Filter string for printable characters
    printable = string.printable.replace( '\r', '' )
    return ''.join(c for c in rawOutput if c in printable )

def getDateTimeFromFile( filePath ):
    dateTime = None
    try:
        with open( filePath, 'r' ) as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if len(line.strip()) == 0:
                continue
            dateTime = datetime.datetime.strptime( line, "%a %b %d %H:%M:%S %Z %Y" )
            break
    except:
        pass
    #if dateTime:
    #	print( "file %s dateTime: %s" % ( filePath, dateTime ) )
    return dateTime

class StressTest(object):
    '''class StressTest( pathToTestTop )
    Path must contain ...
    '''
    def __init__( self, pathToTestTop ):
        self._pathToTestTop	= pathToTestTop
        self._clientList = []
        self._testDuration = None
        self._startTest = None

    def startTest( self ):
        self._startTest = datetime.datetime.now()
        print( "Start:   %s at %s" % ( self._pathToTestTop, self._startTest.strftime("%c") ) )
        try:
            # Remove any stale stopTest file
            os.remove( os.path.join( self._pathToTestTop, "stopTest" ) )
        except:
            pass

    def stopTest( self ):
        print( "Stop:    %s" % self._pathToTestTop )
        activeTests.remove( self )

    def monitorTest( self ):
        print( "Monitor: %s" % self._pathToTestTop )
        stopTime = self.getStopTime()
        if stopTime:
            currentTime = datetime.datetime.now()
            if currentTime > stopTime:
                self.stopTest()

    def getTestTop( self ):
        return self._pathToTestTop

    def getTestDuration( self ):
        return self._testDuration

    def getStopTime( self ):
        stopTime = getDateTimeFromFile( os.path.join( self._pathToTestTop, "stopTest" ) )
        if self._testDuration is not None:
            schedStop = self._startTest + datetime.timedelta( seconds=self._testDuration )
            if not stopTime or stopTime > schedStop:
                stopTime = schedStop
        #if stopTime:
        #	print( "test %s stopTime: %s" % ( self._pathToTestTop, stopTime ) )
        return stopTime

def isActiveTest( pathToTestTop ):
    for test in activeTests:
        if pathToTestTop == test.getTestTop():
            return True
    return False

def checkStartTest( startTestPath, options ):
    stressTestTop = os.path.split( startTestPath )[0]
    if isActiveTest( stressTestTop ):
        return
    #print( "checkStartTime( %s )" % ( startTestPath ) )
    currentTime = datetime.datetime.now()
    startTime = getDateTimeFromFile( startTestPath )
    if startTime is None:
        return

    timeSinceStart = currentTime - startTime
    if timeSinceStart.total_seconds() > 2:
        #print( "checkStartTime( %s ) was %d seconds ago." % ( startTestPath, timeSinceStart.total_seconds() ) )
        return

    stressTest = StressTest( stressTestTop )
    activeTests.append( stressTest )
    stressTest.startTest()
    return

# Pre-compile regular expressions for speed
macroDefRegExp        = re.compile( r"^\s*([a-zA-Z0-9_]*)\s*=\s*(\S*)\s*$" )
macroDefQuotedRegExp  = re.compile( r"^\s*([a-zA-Z0-9_]*)\s*=\s*'([^']*)'\s*$" )
macroDefDQuotedRegExp = re.compile( r'^\s*([a-zA-Z0-9_]*)\s*=\s*"([^"]*)"\s*$' )
macroRefRegExp        = re.compile( r"^([^\$]*)\$([a-zA-Z0-9_]+)(.*)$" )

def expandMacros( strWithMacros, macroDict ):
    #print( "expandMacros(%s)" % strWithMacros )
    global macroRefRegExp
    if type(strWithMacros) is list:
        expandedStrList = []
        for unexpandedStr in strWithMacros:
            expandedStr = expandMacros( unexpandedStr, macroDict )
            expandedStrList += [ expandedStr ]
        return expandedStrList

    while True:
        macroMatch = macroRefRegExp.search( strWithMacros )
        if not macroMatch:
            break
        macroName = macroMatch.group(2)
        if macroName in macroDict:
            # Expand this macro and continue
            strWithMacros = macroMatch.group(1) + macroDict[macroName] + macroMatch.group(3)
            #print( "expandMacros: Expanded %s in %s ..." % ( macroName, strWithMacros ) )
            continue
        # Check for other macros in the string
        return macroMatch.group(1) + '$' + macroMatch.group(2) + expandMacros( macroMatch.group(3), macroDict )
    return strWithMacros

def hasMacros( strWithMacros ):
    global macroRefRegExp
    macrosFound = False
    if type(strWithMacros) is list:
        for unexpandedStr in strWithMacros:
            if ( hasMacros( unexpandedStr ) ):
                macrosFound = True
        return macrosFound

    if macroRefRegExp.search( strWithMacros ) is not None:
        macrosFound = True
    return macrosFound

def getClientConfig( config, clientName ):
    for c in config.get('servers'):
        if c.get('CLIENT_NAME') == clientName:
            return c
    for c in config.get('clients'):
        if c.get('CLIENT_NAME') == clientName:
            return c
    return None

def getEnvFromFile( fileName, env, verbose=False ):
    if verbose:
        print( "getEnvFromFile: %s" % fileName )
    try:
        with open( fileName, 'r' ) as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    continue
                match = (	macroDefRegExp.search(line) or \
                            macroDefQuotedRegExp.search(line) or \
                            macroDefDQuotedRegExp.search(line)	)
                if not match:
                    continue
                macroName = match.group(1)
                macroValue = match.group(2)
                env[macroName] = macroValue
                if verbose:
                    print( "getEnvFromFile: %s = %s" % ( macroName, macroValue ) )
    except:
        pass
    return env

def readClientConfig( clientConfig, clientName, verbose=False ):
    '''Duplicates the readIfFound env handling in launch_client.sh.'''
    clientConfig[ 'CLIENT_NAME' ] = clientName
    SCRIPTDIR  = clientConfig[ 'SCRIPTDIR' ]
    testTop    = clientConfig[ 'TEST_TOP' ]
    getEnvFromFile( os.path.join( SCRIPTDIR, 'stressTestDefault.env' ), clientConfig, verbose=verbose )
    getEnvFromFile( os.path.join( SCRIPTDIR, 'stressTestDefault.env.local' ), clientConfig, verbose=verbose )
    getEnvFromFile( os.path.join( testTop, '..', 'siteDefault.env' ), clientConfig, verbose=verbose )
    getEnvFromFile( os.path.join( testTop, 'siteDefault.env' ), clientConfig, verbose=verbose )
    #getEnvFromFile( os.path.join( TEST_HOST_DIR, 'host.env' ), clientConfig, verbose=verbose )
    getEnvFromFile( os.path.join( testTop, 'test.env' ), clientConfig, verbose=verbose )

    # Read env from clientName.env to get TEST_APPTYPE
    if 'TEST_APPTYPE' in clientConfig:
        print( "TODO: TEST_APPTYPE %s already defined in %s clientConfig!" % ( clientConfig['TEST_APPTYPE'], clientName ) )
    else:
        getEnvFromFile( os.path.join( testTop, clientName + '.env' ), clientConfig, verbose=verbose )
    if 'TEST_APPTYPE' in clientConfig:
        getEnvFromFile( os.path.join( SCRIPTDIR, clientConfig['TEST_APPTYPE'] + 'Default.env' ), clientConfig, verbose=verbose )
        # Reread env from clientName.env to override ${TEST_APPTYPE}Default.env
        getEnvFromFile( os.path.join( testTop, clientName + '.env' ), clientConfig, verbose=verbose )

    # Make sure PYPROC_ID isn't in the clientConfig so it doesn't get expanded
    if 'PYPROC_ID' in clientConfig:
        del clientConfig['PYPROC_ID']

    # Expand macros in clientConfig
    for key in clientConfig:
        clientConfig[key] = expandMacros( clientConfig[key], clientConfig )

    return clientConfig

def runRemote( *args, **kws ):
    config = args[0]
    clientName = args[1]
    testTop = config[ 'TEST_TOP' ]
    verbose = kws.get( 'verbose', False )

    if verbose:
        print( "runRemote client %s:" % clientName )

    clientConfig = getClientConfig( config, clientName )
    if not clientConfig:
        print( "runRemote client %s unable to read test config!" % clientName )
        return None

    TEST_START_DELAY = clientConfig.get( 'TEST_START_DELAY', 0 )
    if TEST_START_DELAY:
        try:
            TEST_START_DELAY  = float(TEST_START_DELAY)
            time.sleep( TEST_START_DELAY )
        except ValueError:
            print( "client %s config has invalid TEST_START_DELAY: %s" % ( clientName, TEST_START_DELAY ) )
    else:
        TEST_START_DELAY  = 0.0

    TEST_LAUNCHER = clientConfig.get('TEST_LAUNCHER')
    TEST_LAUNCHER = expandMacros( TEST_LAUNCHER, clientConfig )
    if hasMacros( TEST_LAUNCHER ):
        print( "runRemote Error: TEST_LAUNCHER has unexpanded macros!\n\t%s\n" % TEST_LAUNCHER )
        return
    hostName  = clientConfig.get('TEST_HOST')
    if not hostName:
        print( "runRemote Error: client %s TEST_HOST not specified!\n" % clientName )
        return
    cmdList = [ 'ssh', '-t', '-t', hostName ]
    cmdList += TEST_LAUNCHER.split()
    sshRemote = subprocess.Popen( cmdList, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE )
    #sshRemote = subprocess.Popen( cmdList, stdin=None, stdout=subprocess.PIPE )
    procList.append( sshRemote )

    TEST_DURATION = clientConfig.get( 'TEST_DURATION' )
    if TEST_DURATION:
        try:
            TEST_DURATION  = float(TEST_DURATION)
            print( "client %s sleeping for TEST_DURATION %f" % ( clientName, TEST_DURATION ), flush=True )
            time.sleep( TEST_DURATION )
        except ValueError:
            print( "client %s config has invalid TEST_DURATION: %s" % ( clientName, TEST_DURATION ) )

        print( "client %s terminate remote" % ( clientName ), flush=True )
        #testRemote.stop()
        sshRemote.terminate()

    while True:
        if verbose:
            print( "client %s fetching output ...\r" % ( clientName ), flush=True )
        try:
            (out,err) = sshRemote.communicate( timeout=1 )
            break
        except subprocess.TimeoutExpired:
            pass

    print( "ssh client %s done." % ( clientName ), flush=True )
    #print( "ssh output type is %s." % ( type(out) ), flush=True )
    return makePrintable( out )

def generateGatewayPVLists( clientConfig, verbose=False ):
    gwPrefix = clientConfig['TEST_GW_PREFIX']
    testTop  = clientConfig['TEST_TOP']
    provider = clientConfig['TEST_PROVIDER']
    gwPvList = []
    if provider == 'pva':
        gwPvList.append( gwPrefix + 'cache' )
        gwPvList.append( gwPrefix + 'clients' )
        gwPvList.append( gwPrefix + 'ds:byhost:rx' )
        gwPvList.append( gwPrefix + 'ds:byhost:tx' )
        gwPvList.append( gwPrefix + 'ds:bypv:rx' )
        gwPvList.append( gwPrefix + 'ds:bypv:tx' )
        gwPvList.append( gwPrefix + 'refs' )
        gwPvList.append( gwPrefix + 'stats' )
        gwPvList.append( gwPrefix + 'us:byhost:rx' )
        gwPvList.append( gwPrefix + 'us:byhost:tx' )
        gwPvList.append( gwPrefix + 'us:bypv:rx' )
        gwPvList.append( gwPrefix + 'us:bypv:tx' )
    elif provider == 'ca':
        gwPvList.append( gwPrefix + 'vctotal' )
        gwPvList.append( gwPrefix + 'pvtotal' )
        gwPvList.append( gwPrefix + 'connected' )
        gwPvList.append( gwPrefix + 'active' )
        gwPvList.append( gwPrefix + 'inactive' )
        gwPvList.append( gwPrefix + 'unconnected' )
        gwPvList.append( gwPrefix + 'connecting' )
        gwPvList.append( gwPrefix + 'disconnected' )
        gwPvList.append( gwPrefix + 'dead' )
        gwPvList.append( gwPrefix + 'clientEventRate' )
        gwPvList.append( gwPrefix + 'clientPostRate' )
        gwPvList.append( gwPrefix + 'existTestRate' )
        gwPvList.append( gwPrefix + 'loopRate' )
        gwPvList.append( gwPrefix + 'cpuFract' )
        gwPvList.append( gwPrefix + 'load' )
        gwPvList.append( gwPrefix + 'serverEventRate' )
        gwPvList.append( gwPrefix + 'serverPostRate' )
    else:
        print( "generateGatewayPVLists: Invalid TEST_PROVIDER: %s" % provider )
        return
    clientHost	 = clientConfig.get( 'TEST_HOST' )
    clientName	 = clientConfig.get( 'CLIENT_NAME' )
    nClients	 = int( clientConfig.get( 'TEST_N_CLIENTS' ) )
    clientPvFileName = os.path.join( testTop, clientHost, 'clients', '%s00' % ( clientName ), "pvs.list" )
    os.makedirs( os.path.dirname( clientPvFileName ), mode=0o775, exist_ok=True )
    print( "generateGatewayPVLists: Writing %d pvs to %s" % ( len(gwPvList), clientPvFileName ) )
    with open( clientPvFileName, 'w' ) as f:
        for pv in gwPvList:
            f.write( "%s\n" % pv )

def generateClientPVLists( testTop, config, verbose=False ):
    '''Create PV Lists for clients.'''
    allCounterPvs = []
    allCircBuffPvs = []
    allRatePvs = []
    servers = config.get( 'servers' )
    for s in servers:
        serverConfig = getClientConfig( config, s.get('CLIENT_NAME') )
        pvPrefix	= serverConfig[ 'TEST_PV_PREFIX' ]
        serverHost	= serverConfig[ 'TEST_HOST' ]
        serverName	= serverConfig[ 'CLIENT_NAME' ]
        nCounters	= int( serverConfig[ 'TEST_N_COUNTERS' ] )
        nServers	= int( serverConfig[ 'TEST_N_SERVERS' ] )
        for iServer in range( nServers ):
            # Generate list of Count and CircBuff PVs for each server
            CounterPvs  = [ "%s%02u:Count%02u"    % ( pvPrefix, iServer, n ) for n in range( nCounters ) ]
            CircBuffPvs = [ "%s%02u:CircBuff%02u" % ( pvPrefix, iServer, n ) for n in range( nCounters ) ]
            RatePvs     = [ "%s%02u:Rate%02u"     % ( pvPrefix, iServer, n ) for n in range( nCounters ) ]
            allCounterPvs  += CounterPvs
            allCircBuffPvs += CircBuffPvs
            allRatePvs += RatePvs

            # Write server pvs.list (not read by loadServer)
            # Each loadServer instance gets it's PV's via $TEST_DB
            serverPvFileName = os.path.join( testTop, serverHost, 'clients', '%s%02u' % ( serverName, iServer ), "pvs.list" )
            os.makedirs( os.path.dirname( serverPvFileName ), mode=0o775, exist_ok=True )
            if verbose:
                print( "generateClientPVLists: Writing %d pvs to\n%s" % ( len(CounterPvs) *3, serverPvFileName ) )
            with open( serverPvFileName, 'w' ) as f:
                for pv in CounterPvs:
                    f.write( "%s\n" % pv )
                for pv in CircBuffPvs:
                    f.write( "%s\n" % pv )
                for pv in RatePvs:
                    f.write( "%s\n" % pv )

    clients = config.get( 'clients' )
    nPvs = len(allCounterPvs)
    for clientConfig in clients:
        appType  = clientConfig.get( 'TEST_APPTYPE' )
        if appType == 'pvGetGateway':
            generateGatewayPVLists( clientConfig, verbose=False )
            continue
        clientHost	  = clientConfig[ 'TEST_HOST' ]
        clientName	  = clientConfig[ 'CLIENT_NAME' ]
        nClients	  = int( clientConfig[ 'TEST_N_CLIENTS' ] )
        nClientsTotal = nClients * len(clients)
        nPvPerClient  = int( len(allCounterPvs) / nClients )
        for iClient in range( nClients ):
            if appType == 'pvGetArray':
                clientPvList  = allCircBuffPvs[ iClient : len(allCircBuffPvs) : nClients ]
            else:
                clientPvList  = allCounterPvs[  iClient : len(allCounterPvs)  : nClients ]
                clientPvList += allRatePvs[     iClient : len(allRatePvs)     : nClients ]
            clientPvFileName  = os.path.join( testTop, clientHost, 'clients', '%s%02u' % ( clientName, iClient ), "pvs.list" )
            os.makedirs( os.path.dirname( clientPvFileName ), mode=0o775, exist_ok=True )
            if verbose:
                print( "generateClientPVLists: Writing %d of %d pvs to\n%s" % ( len(clientPvList), nPvs, clientPvFileName ) )
            with open( clientPvFileName, 'w' ) as f:
                for pv in clientPvList:
                    f.write( "%s\n" % pv )
    return

def clientFetchResult( future ):
    clientName = testFutures[future]
    try:
        clientResult = future.result()
    except Exception as e:
        print( "%s: Exception: %s" % ( clientName, e ) )
    else:
        print( "clientResult for %s:" % ( clientName ) )
        if clientResult:
            #print( "clientResult type is %s." % ( type(clientResult) ), flush=True )
            #if isinstance( clientResult, str ) and clientResult.startswith( "b'" ):
            #	clientResult = eval(clientResult)
            #	print( "eval clientResult type is %s." % ( type(clientResult) ), flush=True )
            #if isinstance( clientResult, bytes ):
            #	clientResult = clientResult.decode()
            #	print( "decoded clientResult type is %s." % ( type(clientResult) ), flush=True )
            clientResult = makePrintable( clientResult )
            #print( "filtered clientResult type is %s." % ( type(clientResult) ), flush=True )
            if isinstance( clientResult, list ):
                for line in clientResult:
                    print( "%s" % line )
            else:
                #if isinstance( clientResult, str ):
                #	clientResult = clientResult.splitlines()
                #	print( "split clientResult type is %s." % ( type(clientResult) ), flush=True )
                print( clientResult )
        else:
            print( clientResult )

def runTest( testTop, config, verbose=False ):
    servers = config.get( 'servers' )
    clients = config.get( 'clients' )
    TEST_NAME = config[ 'TEST_NAME' ]
    if verbose:
        print( "runTest %s for %d servers and %d clients:" % ( TEST_NAME, len(servers), len(clients) ) )
        for s in servers:
            print( "%20s: host %16s, TEST_LAUNCHER: %s" % ( s.get('CLIENT_NAME'), s.get('TEST_HOST'), s.get('TEST_LAUNCHER') ) )
        for c in clients:
            print( "%20s: host %16s, TEST_LAUNCHER: %s" % ( c.get('CLIENT_NAME'), c.get('TEST_HOST'), c.get('TEST_LAUNCHER') ) )

    # Update test configuration
    with open( os.path.join( testTop, 'testConfig.json' ), 'w' ) as f:
        f.write( '# Generated file: Updated on each test run from $TEST_TOP/*.env\n' )
        pprint.pprint( config, stream = f )

    # Create PV lists
    generateClientPVLists( testTop, config, verbose=verbose )

    global testExecutor
    global testFutures
    testExecutor = concurrent.futures.ThreadPoolExecutor( max_workers=None )
    testFutures  = {}
    for c in servers:
        clientName = c.get('CLIENT_NAME')
        testFutures[ testExecutor.submit( runRemote, config, clientName, verbose=verbose ) ] = clientName
    for c in clients:
        clientName = c.get('CLIENT_NAME')
        testFutures[ testExecutor.submit( runRemote, config, clientName, verbose=verbose ) ] = clientName

    print( "Launched %d testFutures ..." % len(testFutures), flush=True )
    for future in testFutures:
        future.add_done_callback( clientFetchResult )

    while True:
        ( done, not_done ) = concurrent.futures.wait( testFutures, timeout=1.0 )
        if len(not_done) == 0:
            break
        if verbose:
            print( "Waiting on %d futures ...\r" % len(not_done) )

    print( "shutdown testExecutor...", flush=True )
    testExecutor.shutdown( wait=True )
    return

def killProcesses( ):
    global procList
    global testDir
    global testFutures

    if testDir:
        killGlob = os.path.join( testDir, "*", "clients", "*.killer" )
        print( 'killProcesses: Checking for killFiles: %s' % killGlob )
        for killFile in glob.glob( os.path.join( testDir, "*", "*.killer" ) ):
            hostName = os.path.split( os.path.split( os.path.split(killFile)[0] )[0] )[1]
            print( 'killProcesses: ssh %s %s' % ( hostName, killFile ), flush=True )
            #subprocess.check_status( "ssh %s %s" % ( hostName, killFile ) )
            # killFile already has "ssh $host pid"
            subprocess.check_status( "%s" % ( killFile ) )
            time.sleep(0.5)

    time.sleep(1.0)
    for proc in procList:
        if proc is not None and proc.returncode is None:
            print( 'killProcesses: kill process %d' % ( proc.pid ), flush=True )
            proc.kill()
            #proc.terminate()

    time.sleep(1.0)
    print( 'killProcesses: Checking %d testFutures ...' % ( len(testFutures) ), flush=True )
    # First kill clients
    for future in testFutures:
        if not future.done():
            clientName = testFutures[future]
            if clientName.find('Server') < 0:
                print( 'killProcesses: Cancel future for %s' % ( clientName ), flush=True )
                time.sleep(0.5)
                future.cancel()

    time.sleep(1.0)
    # kill remaining futures
    for future in testFutures:
        if not future.done():
            clientName = testFutures[future]
            print( 'killProcesses: Cancel future for %s' % ( clientName ), flush=True )
            time.sleep(0.5)
            future.cancel()

    print( 'killProcesses: Shutdown testExecutor', flush=True )
    time.sleep(0.5)
    testExecutor.shutdown( wait=True )

def stressTest_signal_handler( signum, frame ):
    print( "\nstressTest_signal_handler: Received signal %d" % signum, flush=True )
    killProcesses()
    print( 'stressTest_signal_handler: done.', flush=True )
    time.sleep(0.5)

# Install signal handler
signal.signal( signal.SIGINT,  stressTest_signal_handler )
signal.signal( signal.SIGTERM, stressTest_signal_handler )
# Can't catch SIGKILL
#signal.signal( signal.SIGKILL, stressTest_signal_handler )


def process_options():
    #if argv is None:
    #	argv = sys.argv[1:]
    description =	'stressTest/testManager.py manages launching one or more remote stressTest clients and/or servers.\n'
    epilog_fmt  =	'\nExamples:\n' \
                    'stressTest/testManager.py -t "/path/to/testTop/*"\n'
    epilog = textwrap.dedent( epilog_fmt )
    parser = argparse.ArgumentParser( description=description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog )
    #parser.add_argument( 'cmd',  help='Command to launch.  Should be an executable file.' )
    #parser.add_argument( 'arg', nargs='*', help='Arguments for command line. Enclose options in quotes.' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )
    parser.add_argument( '-t', '--testDir', action="store", required=True, help='Path to test directory. Can contain * and other glob syntax.' )

    options = parser.parse_args( )

    return options 

def main( options, argv=None):
    #if options.verbose:
    #	print( "logDir=%s\n" % options.logDir )
    if options.verbose:
        print( "testDir=%s\n" % options.testDir )

    global testDir
    testDir = options.testDir

    testConfig = {}
    servers = []
    clients = []
    # Read test.env
    SCRIPTDIR = os.path.abspath( os.path.dirname( __file__ ) )
    TEST_NAME = os.path.split(testDir)[1]
    testConfig[ 'SCRIPTDIR'] = SCRIPTDIR 
    testConfig[ 'TEST_NAME'] = TEST_NAME
    testConfig[ 'TEST_TOP' ] = testDir
    getEnvFromFile( os.path.join( options.testDir, "test.env" ), testConfig, verbose=options.verbose )
    for envFile in glob.glob( os.path.join( options.testDir, "*.env" ) ):
        baseName = os.path.split( envFile )[1]
        if baseName == "test.env":
            continue

        # Client configuration
        clientConfig = testConfig.copy()
        clientName = baseName.replace( ".env", "" )
        readClientConfig( clientConfig, clientName, verbose=options.verbose )

        if baseName.find( "Server" ) >= 0:
            servers.append( clientConfig.copy() )
        else:
            clients.append( clientConfig.copy() )

    testConfig[ 'servers' ] = servers
    testConfig[ 'clients' ] = clients

    return runTest( options.testDir, testConfig, verbose=options.verbose )

if __name__ == '__main__':
    status = 0
    options = process_options()
    debug = 1

    if debug:
        status = main( options )
    try:
        if not debug:
            status = main( options )
        print( "main() status=" , status )

    except BaseException as e:
        print( e )
        print( "Caught exception during main!" )
        pass

    # Kill any processes still running
    killProcesses()

    sys.exit(status)
