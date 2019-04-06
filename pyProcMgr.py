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
import sys
import os
import io
import locale
#import socket
import subprocess
import argparse
#import readline
#import shutil
import tempfile
import textwrap
import time

procList = []

def launchProcess( command, procNumber=1, verbose=False ):
    # No I/O supported for these processes
    # devnull = os.devnull
    procEnv = os.environ
    procEnv['PYPROC_ID'] = str(procNumber)
    devnull = subprocess.DEVNULL
    procCmd = [ '/afs/slac/g/lcls/epics/extensions/R0.4.0/bin/rhel6-x86_64/procServ', str(40000 + procNumber) ]
    cmdArgs = ' '.join(command).split()
    if verbose:
        print( "launchProcess: %s\n" % cmdArgs )
    procInput = tempfile.TemporaryFile( mode='w+' )
    #procInput = subprocess.PIPE
    procCreationFlags = 0
    proc = None
    testInput = "date >> /tmp/pyproc_%d.log\n" % procNumber
    try:
        if hasattr(procInput,"write"):
            procInput.write( testInput )
        proc = subprocess.Popen(	procCmd + cmdArgs, stdin=procInput, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    env=procEnv, universal_newlines=True )
        if verbose:
            print( "Launched PID: %d" % proc.pid )
        #proc.poll()
        #time.sleep(1)
        #(procOut,procErr) = proc.communicate( testInput )
        #time.sleep(1)
        #if hasattr( proc.stdin, "write" ):
        #	proc.stdin.write( testInput )
        #elif hasattr(procInput,"closed") and not procInput.closed:
        #	procInput.write( testInput )
        #proc.poll()
        #time.sleep(1)
        #(procOut,procErr) = proc.communicate( testInput )
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
    if verbose and proc is not None:
        print( "Returning proc w/ PID: %d" % proc.pid )
    return ( proc, proc.stdin )

def killProcess( proc, verbose=False ):
    if verbose:
        print( "killProcess: %d\n" % proc.pid )
    #proc.signal( os.sigKILL )
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
    if options.verbose:
        print( "Cmd:  %s" % options.cmd )
        print( "Args: %s" % options.arg )
        print( "Full: %s %s" % ( options.cmd, args ) )

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
    except:
        pass

    for procPair in procList:
        proc = procPair[0]
        procInput = procPair[1]
        if hasattr( procInput, 'close' ):
            procInput.close()
        if proc is not None:
            killProcess( proc, verbose=True )

    sys.exit(status)
