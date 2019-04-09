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
import subprocess
import sys
import tempfile
import textwrap
import time

procList = []

# Pre-compile regular expressions for speed
macroRefRegExp      = re.compile( r"^(.*)\$([a-zA-Z0-9_]+)(.*)$" )

def expandMacros( strWithMacros, macroDict ):
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
            continue
        # Check for other macros in the string
        return macroMatch.group(1) + '$' + macroMatch.group(2) + expandMacros( macroMatch.group(3), macroDict )
    return strWithMacros

def launchProcess( command, procNumber=1, verbose=False ):
    # No I/O supported or collected for these processes
    procEnv = os.environ
    procEnv['PYPROC_ID'] = str(procNumber)

    # Expand macros including PYPROC_ID in the command string
    command = expandMacros( command, procEnv )

    devnull = subprocess.DEVNULL
    procName = "pyProc_%d" % procNumber
    procServExe = 'procServ'
    procCmd = [ procServExe, '-f', '--name', procName, str(40000 + procNumber) ]
    cmdArgs = ' '.join(command).split()
    if verbose:
        print( "launchProcess: %s\n" % ' '.join(cmdArgs) )
    proc = None
    try:
        proc = subprocess.Popen(	procCmd + cmdArgs, stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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

def killProcess( proc, verbose=False ):
    if verbose:
        print( "killProcess: %d\n" % proc.pid )
    proc.kill()

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
    parser.add_argument( '-c', '--count',  action="store", default=1, help='Number of processes to launch.' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )

    options = parser.parse_args( )

    return options 

def main(argv=None):
    global procList
    options = process_options(argv)
    args = ' '.join( options.arg )
    #if options.verbose:
    #	print( "Full Cmd: %s %s" % ( options.cmd, args ) )

    try:
        ( proc, procInput ) = launchProcess( [ options.cmd ] + options.arg, verbose=options.verbose )
        if proc is not None:
            procList.append( [ proc, procInput ] )
    except:
        pass

    time.sleep(1)
    print( "Waiting for %d processes:" % len(procList) )
    for procPair in procList:
        procPair[0].wait()

    print( "Done:" )
    return 0

if __name__ == '__main__':
    status = 0
    try:
        status = main()
    except BaseException as e:
        print( e )
        pass

    for procPair in procList:
        proc = procPair[0]
        procInput = procPair[1]
        if hasattr( procInput, 'close' ):
            procInput.close()
        if proc is not None:
            killProcess( proc, verbose=True )

    sys.exit(status)
