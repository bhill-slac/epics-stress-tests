#!/usr/bin/env python3
import argparse
import textwrap
import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.style
matplotlib.style.use( 'seaborn-whitegrid' )

#from matplotlib.font_manager import FontProperties
from stressTest import *

def viewPlots( sTest, level=2, block=True ):
    plotMissRates( sTest, level=level, block=False )
    plotTimeoutRates( sTest, level=level, block=False )
    plotCaptureRates( sTest, level=level, block=block )

def plotCaptureRates( sTest, level=2, block=True ):
    figTitle = 'stressTest %s PV Rates' % sTest._testName
    #fig1 = plt.figure( figTitle, figsize=(20,30) )
    fig1, ax1  = plt.subplots( 1, 1 )
    ax1.set_title(figTitle)

    startTime = sTest.getStartTime()
    numPlots = 0
    sortedClientNames = list(sTest._testClients.keys())
    sortedClientNames.sort()
    for clientName in sortedClientNames:
        client = sTest._testClients[clientName]
        if client.getClientType() != 'pvCapture':
            continue
        testPVs = client.getTestPVs()
        for pvName in testPVs:
            testPV      = testPVs[pvName]
            tsRates     = testPV.getTsRates()
            if len(tsRates) == 0:
                continue
            times  = np.array( list( tsRates.keys()   ) )
            values = np.array( list( tsRates.values() ) )
            if startTime:
                times  -= int(startTime)
            plt.plot( times, values, label=pvName )
            numPlots = numPlots + 1

    if numPlots == 0:
        print( "No PV rate data to plot." )
        return

    if numPlots <= 10:
        #ax1.legend( loc='upper right')
        ax1.legend( loc='best', fontsize='small' )
    plt.draw()
    plt.show(block=block)

def plotMissRates( sTest, level=2, block=True ):
    figTitle = 'stressTest %s PV Missed Count Rates' % sTest._testName
    #fig1 = plt.figure( figTitle, figsize=(20,30) )
    fig1, ax1  = plt.subplots( 1, 1 )
    ax1.set_title(figTitle)

    startTime = sTest.getStartTime()
    numPlots = 0
    sortedClientNames = list(sTest._testClients.keys())
    sortedClientNames.sort()
    for clientName in sortedClientNames:
        client = sTest._testClients[clientName]
        testPVs = client.getTestPVs()
        for pvName in testPVs:
            testPV = testPVs[pvName]
            tsMissRates      = testPV.getTsMissRates()
            if len(tsMissRates) == 0:
                continue
            times  = np.array( list( tsMissRates.keys()   ) )
            values = np.array( list( tsMissRates.values() ) )
            if startTime:
                times  -= int(startTime)
            plt.plot( times, values, label=pvName )
            numPlots = numPlots + 1

    if numPlots == 0:
        print( "No counter miss rate data to plot." )
        return

    if numPlots <= 10:
        #legendFontProp = FontProperties()
        #legendFontProp.set_size('small')
        #ax1.legend( loc='best', prop=legendFontProp )
        ax1.legend( loc='best', fontsize='small' )
    plt.draw()
    plt.show(block=block)

def plotTimeoutRates( sTest, level=2, block=True ):
    figTitle = 'stressTest %s pvget timeout Rates' % sTest._testName
    #fig1 = plt.figure( figTitle, figsize=(20,30) )
    fig1, ax1  = plt.subplots( 1, 1 )
    ax1.set_title(figTitle)

    startTime = sTest.getStartTime()
    numPlots = 0
    sortedClientNames = list(sTest._testClients.keys())
    sortedClientNames.sort()
    for clientName in sortedClientNames:
        client = sTest._testClients[clientName]
        if client.getClientType() != 'pvget':
            continue
        testPVs = client.getTestPVs()
        for pvName in testPVs:
            testPV          = testPVs[pvName]
            timeoutRates    = testPV.getTimeoutRates()
            if len(timeoutRates) == 0:
                continue
            times  = np.array( list( timeoutRates.keys()      ) )
            values = np.array( list( timeoutRates.values() ) )
            if startTime:
                times  -= int(startTime)
            plt.plot( times, values, label=pvName )
            numPlots = numPlots + 1

    if numPlots == 0:
        print( "No PV timeout rate data to plot." )
        return

    if numPlots <= 10:
        #ax1.legend( loc='upper right')
        ax1.legend( loc='best', fontsize='small' )
    plt.draw()
    plt.show(block=block)

def process_options(argv):
    if argv is None:
        argv = sys.argv[1:]
    description =   'stressTestView supports viewing results from CA or PVA network stress tests.\n'
    epilog_fmt  =   '\nExamples:\n' \
                    'stressTestView PATH/TO/TEST/TOP"\n'
    epilog = textwrap.dedent( epilog_fmt )
    parser = argparse.ArgumentParser( description=description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog )
    #parser.add_argument( 'cmd',  help='Command to launch.  Should be an executable file.' )
    #parser.add_argument( 'arg', nargs='*', help='Arguments for command line. Enclose options in quotes.' )
    #parser.add_argument( '-c', '--count',  action="store", type=int, default=1, help='Number of processes to launch.' )
    #parser.add_argument( '-d', '--delay',  action="store", type=float, default=0.0, help='Delay between process launch.' )
    parser.add_argument( '--noPlot',    action="store_true", help='Suppress plot popups.' )
    parser.add_argument( '-t', '--top',  action="store", help='Top directory of test results.' )
    parser.add_argument( '-r', '--report',   action="store", type=int, default=2, help='Set report level.    Higher numbers show more detail.' )
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
        test1.report( options.report )
        if not options.noPlot:
            viewPlots( test1, options.report )

    #if options.verbose:
    #   print( "Full Cmd: %s %s" % ( options.cmd, args ) )
    #   print( "logDir=%s" % options.logDir )

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

    #sys.exit(status)
