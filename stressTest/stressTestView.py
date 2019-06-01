#!/usr/bin/env python3
import argparse
import textwrap
import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt

from stressTest import *

def viewPlots( sTest, level=2, block=True ):
    sTest.plotRates( level=level, block=False )
    sTest.plotMissRates( level=level, block=block )

def plotRates( sTest, level=2, block=True ):
    figTitle = 'stressTest %s PV Rates' % sTest._testName
    #fig1 = plt.figure( figTitle, figsize=(20,30) )
    fig1, ax1  = plt.subplots( 1, 1 )
    ax1.set_title(figTitle)

    numPlots = 0
    for clientName in sTest._testClients:
        client = sTest._testClients[clientName]
        testPVs = client.getTestPVs()
        numPlots = numPlots + len(testPVs.keys())
        for pvName in testPVs:
            testPV = testPVs[pvName]
            tsRates          = testPV.getTsRates()
            tsMissRates      = testPV.getTsMissRates()
            times  = np.array( list( tsRates.keys()   ) )
            values = np.array( list( tsRates.values() ) )
            plt.plot( times, values, label=pvName )

    if numPlots <= 10:
        ax1.legend( loc='upper right')
    plt.draw()
    plt.show(block=block)

def plotMissRates( sTest, level=2, block=True ):
    figTitle = 'stressTest %s PV Missed Count Rates' % sTest._testName
    #fig1 = plt.figure( figTitle, figsize=(20,30) )
    fig1, ax1  = plt.subplots( 1, 1 )
    ax1.set_title(figTitle)

    numPlots = 0
    for clientName in sTest._testClients:
        client = sTest._testClients[clientName]
        testPVs = client.getTestPVs()
        numPlots = numPlots + len(testPVs.keys())
        for pvName in testPVs:
            testPV = testPVs[pvName]
            #tsRates          = testPV.getTsRates()
            tsMissRates      = testPV.getTsMissRates()
            times  = np.array( list( tsMissRates.keys()   ) )
            values = np.array( list( tsMissRates.values() ) )
            plt.plot( times, values, label=pvName )

    if numPlots <= 10:
        ax1.legend( loc='upper right')
    plt.draw()
    plt.show(block=block)

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
        test1.report( level = 2 )
        viewPlots( test1, level = 2 )

    #if options.verbose:
    #	print( "Full Cmd: %s %s" % ( options.cmd, args ) )
    #	print( "logDir=%s" % options.logDir )

if __name__ == '__main__':
    status = 0
    DEV = True
    if DEV:
        status = main()
    else:
        # Catching the exception is better for users, but
        # less usefull during development.
        try:
            status = main()
        except BaseException as e:
            print( "Caught exception during main!" )
            print( e )

    # Pre-exit cleanup
    #killProcesses()

    sys.exit(status)
