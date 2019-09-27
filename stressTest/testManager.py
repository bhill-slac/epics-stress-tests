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

        #testEnv = os.environ
        #testEnv[ 'STRESS_TESTS' ] = '/reg/d/iocData/gwTest'
        #testEnv[ 'TEST_NAME' ] = 'oneHostOneCounter'

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
        if c.get('name') == clientName:
            return c
    for c in config.get('clients'):
        if c.get('name') == clientName:
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

def getClientEnv( testTop, clientName, verbose=False ):
    '''Starts from os environment then duplicates the readIfFound env handling in launch_client.sh.'''
    clientEnv = dict(os.environ)
    SCRIPTDIR = os.path.abspath( os.path.dirname( __file__ ) )
    clientEnv[ 'CLIENT_NAME'] = clientName 
    clientEnv[ 'TEST_TOP'] = testTop 
    clientEnv[ 'SCRIPTDIR'] = SCRIPTDIR 
    clientEnv = getEnvFromFile( os.path.join( SCRIPTDIR, 'stressTestDefault.env' ), clientEnv, verbose=verbose )
    getEnvFromFile( os.path.join( testTop, '..', 'siteDefault.env' ), clientEnv, verbose=verbose )
    getEnvFromFile( os.path.join( testTop, 'siteDefault.env' ), clientEnv, verbose=verbose )
    #HOSTNAME = socket.gethostname()
    #clientEnv[ 'HOSTNAME' ] = HOSTNAME
    #TEST_HOST_DIR = os.path.join( testTop, HOSTNAME )
    #clientEnv[ 'TEST_HOST_DIR' ] = TEST_HOST_DIR
    #clientEnv[ 'TEST_DIR' ] = os.path.join( TEST_HOST_DIR, 'clients' )
    #getEnvFromFile( os.path.join( TEST_HOST_DIR, 'host.env' ), clientEnv, verbose=verbose )
    getEnvFromFile( os.path.join( testTop, 'test.env' ), clientEnv, verbose=verbose )

    # Read env from clientName.env to get TEST_APPTYPE
    getEnvFromFile( os.path.join( testTop, clientName + '.env' ), clientEnv, verbose=verbose )
    if 'TEST_APPTYPE' in clientEnv:
        getEnvFromFile( os.path.join( SCRIPTDIR, clientEnv['TEST_APPTYPE'] + 'Default.env' ), clientEnv, verbose=verbose )
        # Reread env from clientName.env to override ${TEST_APPTYPE}Default.env
        getEnvFromFile( os.path.join( testTop, clientName + '.env' ), clientEnv, verbose=verbose )

    # Make sure PYPROC_ID isn't in the clientEnv so it doesn't get expanded
    if 'PYPROC_ID' in clientEnv:
        del clientEnv['PYPROC_ID']

    return clientEnv

def runRemote( *args, **kws ):
    config = args[0]
    clientName = args[1]
    testTop = config[ 'TEST_TOP' ]
    verbose = kws.get( 'verbose', False )

    if verbose:
        print( "runRemote client %s:" % clientName )

    clientEnv = getClientEnv( testTop, clientName, verbose=verbose )
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

    launcher = clientConfig.get('launcher')
    launcher = expandMacros( launcher, clientEnv )
    if hasMacros( launcher ):
        print( "runRemote Error: launcher has unexpanded macros!\n\t%s\n" % launcher )
        return
    hostName  = clientConfig.get('TEST_HOST')
    if not hostName:
        print( "runRemote Error: client %s TEST_HOST not specified!\n" % clientName )
        return
    cmdList = [ 'ssh', '-t', '-t', hostName ]
    cmdList += launcher.split()
    sshRemote = subprocess.Popen( cmdList, stdout=subprocess.PIPE )
    #testRemote = stressTestRemote( clientConfig )
    #testRemote.start()

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

    if True:
        while True:
            if verbose:
                print( "client %s fetching output ..." % ( clientName ), flush=True )
            try:
                (out,err) = sshRemote.communicate( timeout=1 )
                break
            except subprocess.TimeoutExpired:
                pass

        print( "ssh client %s done." % ( clientName ), flush=True )
        #print( "ssh output type is %s." % ( type(out) ), flush=True )
        return makePrintable( out )
    else:
        return None

def generateClientPVLists( testTop, config, verbose=False ):
    '''Create PV Lists for clients.'''
    # TODO: generate PV lists
    totalPvList = []
    servers = config.get( 'servers' )
    for s in servers:
        serverEnv	= getClientEnv( testTop, s.get('name'), verbose=verbose )
        pvPrefix	= serverEnv[ 'TEST_PV_PREFIX' ]
        nCounters	= int( serverEnv[ 'TEST_N_COUNTERS' ] )
        nServers	= int( serverEnv[ 'TEST_N_SERVERS' ] )
        for iServer in range( nServers ):
            pvList = [ "%s%02u:Count%02u" % ( pvPrefix, iServer, n ) for n in range( nCounters ) ]
            totalPvList += pvList
            if verbose:
                print( "%20s%02d: %s" % ( s.get('name'), iServer, pvList ), flush=True )

    clients = config.get( 'clients' )
    nPvs = len(totalPvList)
    for clientConfig in clients:
        clientHost	 = clientConfig.get( 'TEST_HOST' )
        clientName	 = clientConfig.get( 'name' )
        nClients	 = int( clientConfig.get( 'TEST_N_CLIENTS' ) )
        nClientsTotal= nClients * len(clients)
        nPvPerClient = int( len(totalPvList) / nClientsTotal )
        for iClient in range( nClients ):
            clientPvList = totalPvList[ iClient : nPvPerClient + 1 : nClientsTotal ]
            clientPvFileName = os.path.join( testTop, clientHost, 'clients', '%s%02u' % ( clientName, iClient ), "pvs.list" )
            os.makedirs( os.path.dirname( clientPvFileName ), mode=0o775, exist_ok=True )
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
    config[ 'TEST_TOP' ] = testTop
    TEST_NAME = os.path.split(testTop)[1]
    config[ 'TEST_NAME' ] = TEST_NAME
    if verbose:
        print( "runTest %s for %d servers and %d clients:" % ( TEST_NAME, len(servers), len(clients) ) )
        for s in servers:
            print( "%20s: host %16s, launcher: %s" % ( s.get('name'), s.get('TEST_HOST'), s.get('launcher') ) )
        for c in clients:
            print( "%20s: host %16s, launcher: %s" % ( c.get('name'), c.get('TEST_HOST'), c.get('launcher') ) )
            #runRemote( config, c.get('name'), verbose=verbose )
    
    # Create PV lists
    generateClientPVLists( testTop, config, verbose=verbose )

    global testExecutor
    global testFutures
    testExecutor = concurrent.futures.ThreadPoolExecutor( max_workers=None )
    testFutures  = {}
    for c in servers:
        clientName = c.get('name')
        testFutures[ testExecutor.submit( runRemote, config, clientName, verbose=verbose ) ] = clientName
    for c in clients:
        clientName = c.get('name')
        testFutures[ testExecutor.submit( runRemote, config, clientName, verbose=verbose ) ] = clientName

    print( "Launched %d testFutures ..." % len(testFutures), flush=True )
    for future in testFutures:
        future.add_done_callback( clientFetchResult )

    while True:
        ( done, not_done ) = concurrent.futures.wait( testFutures, timeout=0.1 )
        if len(not_done) == 0:
            break

    print( "shutdown testExecutor...", flush=True )
    testExecutor.shutdown( wait=True )
    return

def launchProcess( command, procNumber=0, procNameBase="stressTest_", basePort=40000, logDir=None, verbose=False ):
    # No I/O supported or collected for these processes
    procEnv = os.environ
    procEnv['PYPROC_ID'] = "%02u" % procNumber
    procName = "%s%02u" % ( procNameBase, procNumber )

    #if verbose:
    #	print( "launchProcess: Unexpanded command:\n\t%s\n" % command )

    # Expand macros including PYPROC_ID in the command string
    command = expandMacros( command, procEnv )
    if hasMacros( command ):
        print( "launchProcess Error: Command has unexpanded macros!\n\t%s\n" % command )
        #print( procEnv )
        return ( None, None )

    logFile = None
    logFileName = None
    devnull = subprocess.DEVNULL
    #procInput = devnull
    procInput = None
    procInput = subprocess.PIPE
    #procOutput = subprocess.STDOUT
    procOutput = None
    procOutput = subprocess.PIPE

    cmdArgs = ' '.join(command).split()
    if verbose:
        print( "launchProcess: %s %s\n" % ( ' '.join(cmdArgs) ), flush=True )
    proc = None
    try:
        proc = subprocess.Popen(	cmdArgs, stdin=procInput, stdout=procOutput, stderr=subprocess.STDOUT,
                                    env=procEnv, universal_newlines=True )
        if verbose:
            print( "Launched %s with PID %d" % ( procName, proc.pid ), flush=True )
    except ValueError as e:
        print( "launchProcess: ValueError" )
        print( e )
        pass
    except OSError as e:
        print( "launchProcess: OSError" )
        print( e )
        pass
    except subprocess.CalledProcessError as e:
        print( "launchProcess: CalledProcessError" )
        print( e )
        pass
    except e:
        print( "Unknown exception thrown" )
        print( e )
        pass
    return ( proc, proc.stdin )

def killProcess( proc, port, verbose=False ):
    #if verbose:
    #	print( "killProcess: %d" % proc.pid )

    try:
        if port is None:
            proc.kill()
        else:
            #procServUtils.killProc( 'localhost', port )
            print( "procServUtils.killProc( localhost, %d )\n" % port )
    except:
        proc.kill()

def terminateProcess( proc, verbose=False ):
    if verbose:
        print( "terminateProcess: %d" % proc.pid )
    proc.terminate()

abortAll	= False
def killProcesses( testDir = None ):
    global abortAll
    global procList
    global testFutures
    abortAll = True
    print( 'killProcesses: Canceling %d testFutures ...' % ( len(testFutures) ), flush=True )
    for future in testFutures:
        if not future.done():
            clientName = testFutures[future]
            print( 'killProcesses: Cancel future for %s' % ( clientName ), flush=True )
            future.cancel()
    testExecutor.shutdown( wait=True )

    for procTuple in procList:
        proc      = procTuple[0]
        procInput = procTuple[1]
        procPort  = procTuple[2]
        if proc is not None:
            print( 'killProcesses: kill process on port %d' % ( procPort ), flush=True )
            killProcess( proc, procPort, verbose=True )
            procTuple[2] = None
        if hasattr( procInput, 'close' ):
            procInput.close()

    if testDir:
        for killFile in glob.glob( os.path.join( testDir, "*", "*.killer" ) ):
            hostName = os.path.split( os.path.split( os.path.split(killFile)[0] )[0] )[1]
            print( 'killProcesses: ssh %s %s' % ( hostName, killFile ), flush=True )
            subprocess.check_status( "ssh %s %s" % ( hostName, killFile ) )

def stressTest_signal_handler( signum, frame ):
    print( "\nstressTest_signal_handler: Received signal %d" % signum, flush=True )
    killProcesses()

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
    parser.add_argument( '-n', '--name',  action="store", default="stressTest_", help='process basename, name is basename + str(procNumber)' )
    parser.add_argument( '-t', '--testDir', action="store", required=True, help='Path to test directory. Can contain * and other glob syntax.' )

    options = parser.parse_args( )

    return options 

def main( options, argv=None):
    global procList
    #if options.verbose:
    #	print( "logDir=%s\n" % options.logDir )
    if options.verbose:
        print( "testDir=%s\n" % options.testDir )

    testConfig = {}
    clients = []
    servers = []
    # Read test.env
    getEnvFromFile( os.path.join( options.testDir, "test.env" ), testConfig, verbose=options.verbose )
    for envFile in glob.glob( os.path.join( options.testDir, "*.env" ) ):
        baseName = os.path.split( envFile )[1]
        if baseName == "test.env":
            continue
        if baseName.find( "Server" ) >= 0:
            # Server configuration
            serverConfig = {}
            serverConfig[ 'name' ] = baseName.replace( ".env", "" )
            serverConfig[ 'launcher'  ] = '$SCRIPTDIR/launch_client.sh $TEST_TOP $CLIENT_NAME'
            getEnvFromFile( envFile, serverConfig, verbose=options.verbose )
            servers.append( serverConfig )
        else:
            # Client configuration
            clientConfig = {}
            clientConfig[ 'name' ] = baseName.replace( ".env", "" )
            clientConfig[ 'launcher'  ] = '$SCRIPTDIR/launch_client.sh $TEST_TOP $CLIENT_NAME'
            getEnvFromFile( envFile, clientConfig, verbose=options.verbose )
            clients.append( clientConfig )
    testConfig[ 'servers' ] = servers
    testConfig[ 'clients' ] = clients

    if testConfig:
        return runTest( options.testDir, testConfig, verbose=options.verbose )

    procNumber = 1
    testInProcess = False
    while True:
        if abortAll:
            break

        #if testInProcess = True and currentTime > loadavgPriorTime + loadavgInterval:
        #	loadavgDumpToHostLog()

        startTest = False
        startTestFiles = glob.glob( os.path.join( options.testDir, "startTest" ) )
        for f in startTestFiles:
            checkStartTest( f, options )

        for test in activeTests:
            test.monitorTest( )

        time.sleep(1.0)
            #clientList = getClientList()
            #for client in clientList:
            #	if client.host() != os.hostname():
            #		continue
            #testEnv = {}
            # testEnv = readTestEnvFiles( $STRESSTEST_TOP/$TEST_NAME, testEnv )
            # testEnv = client.testEnv()
            # client.setup()
            # client.launch()
            #try:
            #	( proc, procInput ) = launchProcess( [ options.cmd ] + options.arg,
            #								procNameBase=options.name,
            #								basePort=options.port,
            #								logDir=options.logDir,
            #	if proc is not None:
            #		procNumber += 1
            #		procList.append( [ proc, procInput, options.port + procNumber ] )
            #								verbose=options.verbose )
            #except BaseException as e:
            #	print( "Error launching proc %d: %s %s" % ( procNumber, options.cmd, args ) )
            #	break

        # if currentTime >= startTime + testDuration:
            #for client in clientList:
            #	if client.host() != os.hostname():
            #		continue
            #	if currentTime >= client.stopTime()
            #		client.stop()

        #if getNumActiveClients() == 0:
        #	testInProcess = False

    #time.sleep(1)
    #print( "Waiting for %d processes:" % len(procList) )
    #for procTuple in procList:
    #	procTuple[0].wait()

    print( "Done:" )
    return 0

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