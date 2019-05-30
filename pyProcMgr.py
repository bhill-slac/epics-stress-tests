#!/usr/bin/env python
#  Name: pyProcMgr.py
#  Abs:  A python tool to launch and manage processes
#
#  Example:
#    pyProcMgr --cmd "echo hello world"
#
#  Requested features to be added:
#
#==============================================================
from __future__ import print_function
import argparse
import io
import locale
import os
import re
import procServUtils
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

procList = []

# Pre-compile regular expressions for speed
macroRefRegExp      = re.compile( r"^([^\$]*)\$([a-zA-Z0-9_]+)(.*)$" )

def expandMacros( strWithMacros, macroDict ):
    #print( "expandMacros(%s)\n" % strWithMacros )
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
            #print( "expandMacros: Expanded %s in %s ...\n" % ( macroName, strWithMacros ) )
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

def launchProcess( command, procNumber=0, procNameBase="pyProc_", basePort=40000, logDir=None, verbose=False ):
    # No I/O supported or collected for these processes
    procEnv = os.environ
    procEnv['PYPROC_ID'] = str(procNumber)

    #print( "launchProcess: Unexpanded command:\n\t%s\n" % command )

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
    procName = "%s%d" % ( procNameBase, procNumber )
    procServExe = 'procServ'
    # Start w/ procServ executable and procServ parameters
    procCmd = [ procServExe ]
    # Set signal to SIGINT so child process gets a clean shutdown.
    #procCmd += [ '--killsig', str(int(signal.SIGINT)) ]
    # Use foreground mode so processes remain child processes and can be cancelled when parent sees Ctrl-C.
    useFgMode = True
    if logDir is not None:
        logFileName	= os.path.join( logDir, procName + ".log" )
    if useFgMode:
        procCmd += [ '-f' ]
        if logFileName is not None:
            try:
                logFile = open( logFileName, "w" )
                # To capture logfile in foreground mode, log to stdout and capture via subprocess
                procCmd += [ '--logfile', '-' ]
                procInput  = devnull
                procOutput = logFile
            except IOError as e:
                print( "IOError: Unable to open %s\n" % logFileName )
                pass
            except OSError as e:
                print( "OSError: Unable to open %s\n" % logFileName )
                pass
    else:
        if logFileName is not None:
            procCmd += [ '--logfile', logFileName ]
    procCmd += [ '--logstamp', '--timefmt', '[%c] ' ]
    procCmd += [ '--name', procName ]
    procCmd += [ '--allow' ]
    procCmd += [ '--noautorestart' ]
    procCmd += [ '--coresize', '0' ]
    # Enable --savelog to save timestamped log files
    #procCmd += [ '--savelog' ]

    # Finish w/ procServ connection port and process command
    procCmd.append( str(basePort + procNumber) )
    cmdArgs = ' '.join(command).split()
    if verbose:
        print( "launchProcess: %s %s\n" % ( ' '.join(procCmd), ' '.join(cmdArgs) ) )
    proc = None
    try:
        proc = subprocess.Popen(	procCmd + cmdArgs, stdin=procInput, stdout=procOutput, stderr=subprocess.STDOUT,
                                    env=procEnv, universal_newlines=True )
        if verbose:
            print( "Launched %s with PID %d" % ( procName, proc.pid ) )
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
            procServUtils.killProc( 'localhost', port )
    except:
        proc.kill()

def terminateProcess( proc, verbose=False ):
    if verbose:
        print( "terminateProcess: %d" % proc.pid )
    proc.terminate()

abortAll	= False
def killProcesses():
    global abortAll
    global procList
    abortAll = True
    for procTuple in procList:
        proc      = procTuple[0]
        procInput = procTuple[1]
        procPort  = procTuple[2]
        if proc is not None:
            killProcess( proc, procPort, verbose=True )
            procTuple[2] = None
        if hasattr( procInput, 'close' ):
            procInput.close()

def pyProc_signal_handler( signum, frame ):
    print( "\npyProc_signal_handler: Received signal %d" % signum )
    killProcesses()

# Install signal handler
signal.signal( signal.SIGINT,  pyProc_signal_handler )
#signal.signal( signal.SIGTERM, pyProc_signal_handler )
# Can't catch SIGKILL
#signal.signal( signal.SIGKILL, pyProc_signal_handler )


def process_options(argv):
    if argv is None:
        argv = sys.argv[1:]
    description =	'pyProcMgr supports launching one or more processes.\n' \
                +	'Command strings w/ arguments should be quoted.\n' \
                +	'pyProcMgr will run as long as any of it\'s child processes are still running,\n' \
                +	'and if killed via Ctrl-C will kill any remaining child processes.'
    epilog_fmt  =	'\nExamples:\n' \
                    'pyProcMgr pvget "-w1 TST:BaseVersion"\n'
    epilog = textwrap.dedent( epilog_fmt )
    parser = argparse.ArgumentParser( description=description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog )
    parser.add_argument( 'cmd',  help='Command to launch.  Should be an executable file.' )
    parser.add_argument( 'arg', nargs='*', help='Arguments for command line. Enclose options in quotes.' )
    parser.add_argument( '-c', '--count',  action="store", type=int, default=1, help='Number of processes to launch.' )
    parser.add_argument( '-d', '--delay',  action="store", type=float, default=0.0, help='Delay between process launch.' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )
    parser.add_argument( '-p', '--port',  action="store", type=int, default=40000, help='Base port number, procServ port is port + str(procNumber)' )
    parser.add_argument( '-n', '--name',  action="store", default="pyProc_", help='process basename, name is basename + str(procNumber)' )
    parser.add_argument( '-D', '--logDir',  action="store", default=None, help='log file directory.' )

    options = parser.parse_args( )

    return options 

def main(argv=None):
    global procList
    options = process_options(argv)
    args = ' '.join( options.arg )
    #if options.verbose:
    #	print( "Full Cmd: %s %s" % ( options.cmd, args ) )

    for procNumber in range(options.count):
        try:
            if abortAll:
                break
            ( proc, procInput ) = launchProcess( [ options.cmd ] + options.arg,
                                                procNumber=procNumber,
                                                procNameBase=options.name,
                                                basePort=options.port,
                                                logDir=options.logDir,
                                                verbose=options.verbose )
            if proc is not None:
                procList.append( [ proc, procInput, options.port + procNumber ] )
        except BaseException as e:
            print( "Error launching proc %d: %s %s" % ( procNumber, options.cmd, args ) )
            break

        try:
            if options.delay > 0.0:
                time.sleep( options.delay )
        except BaseException as e:
            raise

    time.sleep(1)
    print( "Waiting for %d processes:" % len(procList) )
    for procTuple in procList:
        procTuple[0].wait()

    print( "Done:" )
    return 0

if __name__ == '__main__':
    status = 0
    try:
        status = main()
    except BaseException as e:
        print( "Caught exception during main!" )
        print( e )
        pass

    # Kill any processes still running
    killProcesses()

    sys.exit(status)
