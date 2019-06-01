#!/usr/bin/env python3
import argparse
import textwrap
import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt

from stressTestClient import *

class stressTest:
    def __init__( self, testName, testPathTop ):
        self._testName = testName
        self._testPath = testPathTop
        self._testClients = {}
        self._testServers = {}
        self._testPVs = {}
        self._gwStats = {}
        self._totalNumPVs      = 0		# Total number of testPVs for all clients
        self._totalNumMissed   = 0		# Total number of cumulative missed counts for all clients and testPVs
        self._totalNumTsValues = 0		# Total number of timestamped values collected for all clients and testPVs
        self._startTime        = None	# Earliest timestamp for test
        self._endTime          = None	# Latest   timestamp for test

    def getEndTime( self ):
        return self._endTime
    def getStartTime( self ):
        return self._startTime
    def getNumClients( self ):
        return len(self._tsClients)
    def getNumServers( self ):
        return len(self._tsServers)
    def getTotalNumPVs( self ):
        ''' Total number of testPVs for all clients. '''
        return self._totalNumPVs
    def getTotalNumMissed( self ):
        '''Total number of cumulative missed counts for all clients and testPVs.'''
        return self._totalNumMissed
    def getTotalNumTsValues( self ):
        '''Total number of timestamped values collected for all clients and testPVs.'''
        return self._totalNumTsValues

    def analyze( self ):
        print( "stressTestView.analyze: %s ..." % self._testName )
        self._endTime   = None
        self._startTime = None
        self._totalNumPVs = 0
        self._totalNumTsValues = 0
        for clientName in self._testClients:
            client = self._testClients[clientName]
            client.analyze()

            # Update totals
            self._totalNumPVs      += client.getNumPVs()
            self._totalNumTsValues += client.getNumTsValues()
            self._totalNumMissed   += client.getNumMissed()

            # Update start and end times
            if  self._startTime is None or self._startTime > client.getStartTime():
                self._startTime =  client.getStartTime()
            if  self._endTime   is None or self._endTime < client.getEndTime():
                self._endTime   =  client.getEndTime()

    def report( self, level=2 ):
        print( "\nStressTest Report:" )
        print( "TestName: %s" % self._testName )
        #totalNumPVs = 0
        #totalNumTsValues = 0
        #totalNumMissed   = 0
        if len(self._testClients):
            print( "Clients                            NumPVs NumTsValues NumMissed" )
            #      "    CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC NNNNNN TTTTTTTTTTT MMMMMMMMM" )
        sortedClientNames = list(self._testClients.keys())
        sortedClientNames.sort()
        for clientName in sortedClientNames:
            client = self._testClients[clientName]
            numPVs           = client.getNumPVs()
            numTsValues      = client.getNumTsValues()
            numMissed        = client.getNumMissed()
            #tsRates          = client.getTsRates()
            #tsMissRates      = client.getTsMissRates()
            #totalNumPVs      = totalNumPVs + numPVs
            #totalNumTsValues = totalNumTsValues + numTsValues
            #totalNumMissed   = totalNumMissed + numMissed
            if level >= 2:
                print( "    %-30s %6u %11u %9u" % ( clientName, numPVs, numTsValues, numMissed ) )
            if level >= 3:
                testPVs = client.getTestPVs()
                sortedPVNames = list(testPVs.keys())
                sortedPVNames.sort()
                for pvName in sortedPVNames:
                    testPV = testPVs[pvName]
                    print( "        %-26s %6u %11u %9u" % ( pvName, 1, testPV.getNumTsValues(), testPV.getNumMissed() ) )
                    if level >= 4:
                        tsRates          = testPV.getTsRates()
                        sortedKeys = list(tsRates.keys())
                        sortedKeys.sort()
                        numShow = min( 20, len(sortedKeys) )
                        print( "        ValueRates: First %u seconds" % numShow )
                        print( "        [", end='' )
                        for t in sortedKeys[0:numShow-2]:
                            print( "%4u" % tsRates[t], end=', ' )
                        t = sortedKeys[numShow-1]
                        print( "%4u" % tsRates[t] )

                        tsMissRates      = testPV.getTsMissRates()
                        numShow = min( 20, len(tsMissRates.keys()) )
                        print( "        MissedValueRates: First %u seconds" % numShow )
                        print( "        [", end='' )
                        for t in list( tsMissRates.keys() )[0:numShow-2]:
                            print( "%4u" % tsMissRates[t], end=', ' )
                        t = list( tsMissRates.keys() )[numShow-1]
                        print( "%4u" % tsMissRates[t] )

        #if level >= 2:
        #	print( "    %-30s %6u %11u %9u" % ( "Total",
        #				self.getTotalNumPVs(), self.getTotalNumTsValues(), self.getTotalNumMissed() ) )
        #else:
        #	print( "    %-30s %6u %11u %9u" % ( str(len(self._testClients)),
        #				self.getTotalNumPVs(), self.getTotalNumTsValues(), self.getTotalNumMissed() ) )
        print( "    %-30s %6u %11u %9u" % ( "Total" if level >= 2 else str(len(self._testClients)),
                    self.getTotalNumPVs(), self.getTotalNumTsValues(), self.getTotalNumMissed() ) )

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

    def readFiles( self, dirTop, analyze = True, verbose = True ):
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

        if analyze:
            self.analyze()
        return

