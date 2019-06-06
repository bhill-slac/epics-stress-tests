#!/usr/bin/env python3
import argparse
import textwrap
import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt

from stressTestClient import *
from stressTestFile import *

class stressTest:
    def __init__( self, testName, testPathTop ):
        self._testName          = testName
        self._testPath          = testPathTop
        self._testClients       = {}    # map of test clients, key is clientName
        self._testFiles         = {}    # map of test files, key is pathTopToFile
        self._testServers       = {}    # map of test servers, key is serverName
        #self._gwStats          = {}
        self._totalNumPVs       = 0     # Total number of testPVs for all clients
        self._totalNumMissed    = 0     # Total number of cumulative missed counts for all clients and testPVs
        self._totalNumTsValues  = 0     # Total number of timestamped values collected for all clients and testPVs
        self._totalNumTimeouts  = 0     # Total number of timeouts collected for all clients and testPVs
        self._startTime        = None   # Earliest timestamp for test
        self._endTime          = None   # Latest   timestamp for test

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
    def getTotalNumTimeouts( self ):
        '''Total number of timeouts collected for all clients and testPVs.'''
        return self._totalNumTimeouts

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
            self._totalNumTimeouts += client.getNumTimeouts()

            # Update start and end times
            if client.getStartTime():
                if  self._startTime is None or self._startTime > client.getStartTime():
                    self._startTime =  client.getStartTime()
            if client.getEndTime():
                if  self._endTime   is None or self._endTime < client.getEndTime():
                    self._endTime   =  client.getEndTime()

    def report( self, level=2 ):
        print( "\nStressTest Report:" )
        print( "TestName: %s" % self._testName )

        # Show files
        if len(self._testFiles):
            typeInfo = {}   # map of fileType to ( numLines, numTsValues )
            sortedFileNames = list(self._testFiles)
            sortedFileNames.sort()
            for fileName in sortedFileNames:
                testFile = self._testFiles[fileName]
                fileInfo = ( testFile.getNumLines(), testFile.getNumTsValues(), testFile.getNumTimeouts() )
                fileType = testFile.getFileType()
                if fileType in typeInfo:
                    ( numPVs, numTsValues, numTimeouts ) = typeInfo[fileType]
                    typeInfo[fileType] = (  fileInfo[0] + numPVs,
                                            fileInfo[1] + numTsValues,
                                            fileInfo[2] + numTimeouts )
                else:
                    typeInfo[fileType] = fileInfo
            print( "    FileTypes  NumLines NumTsValues NumTimeouts" )
            #      "    TTTTTTTTTT NNNNNNNN TTTTTTTTTTT TTTTTTTTTTT" )
            for fileType in typeInfo:
                ( numPVs, numTsValues, numTimeouts ) = typeInfo[fileType]
                print(  "    %-10s %8u %11u %11u" % (fileType, numPVs, numTsValues, numTimeouts) )

        # Show clients
        if len(self._testClients):
            print( "Clients                            NumPVs NumTsValues NumMissed Timeouts" )
            #      "    CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC NNNNNN TTTTTTTTTTT MMMMMMMMM TTTTTTTT" )
        sortedClientNames = list(self._testClients.keys())
        sortedClientNames.sort()
        for clientName in sortedClientNames:
            client = self._testClients[clientName]
            numPVs           = client.getNumPVs()
            numTsValues      = client.getNumTsValues()
            numMissed        = client.getNumMissed()
            numTimeouts      = client.getNumTimeouts()
            #tsRates          = client.getTsRates()
            #tsMissRates      = client.getTsMissRates()
            if level >= 2:
                print( "    %-30s %6u %11u %9u %8u" % ( clientName, numPVs, numTsValues, numMissed, numTimeouts ) )
            if level >= 3:
                testPVs = client.getTestPVs()
                sortedPVNames = list(testPVs.keys())
                sortedPVNames.sort()
                for pvName in sortedPVNames:
                    testPV = testPVs[pvName]
                    print( "        %-26s %6u %11u %9u %8u" % ( pvName, 1, testPV.getNumTsValues(), testPV.getNumMissed(), testPV.getNumTimeouts() ) )
                    if level >= 4:
                        tsRates          = testPV.getTsRates()
                        sortedKeys = list(tsRates.keys())
                        sortedKeys.sort()
                        numShow = min( 10, len(sortedKeys) )
                        print( "        ValueRates: First %u: [ " % numShow, end='' )
                        for t in sortedKeys[0:numShow-2]:
                            print( "(%.3f, %4u), " % ( t, tsRates[t] ), end=', ' )
                        if len(sortedKeys) > 0:
                            t = sortedKeys[numShow-1]
                            print( "(%.3f,%4u) ]" % ( t, tsRates[t] ) )

                        tsMissRates      = testPV.getTsMissRates()
                        numShow = min( 10, len(tsMissRates.keys()) )
                        print( "        TsMissedRates: First %u: [ " % numShow, end='' )
                        for t in list( tsMissRates.keys() )[0:numShow-2]:
                            print( "(%.3f, %4u), " % ( t, tsMissRates[t] ), end=', ' )
                        if len(tsMissRates) > 0:
                            t = list( tsMissRates.keys() )[numShow-1]
                            print( "(%.3f, %4u) ]" % ( t, tsMissRates[t] ) )

                        timeoutRates         = testPV.getTimeoutRates()
                        numShow = min( 10, len(timeoutRates.keys()) )
                        print( "        TimeoutRates: First %u: [ " % numShow, end='' )
                        for t in list( timeoutRates.keys() )[0:numShow-2]:
                            print( "(%.3f, %4u), " % ( t, timeoutRates[t] ), end=', ' )
                        if len(timeoutRates) > 0:
                            t = list( timeoutRates.keys() )[numShow-1]
                            print( "(%.3f, %4u) ]" % ( t, timeoutRates[t] ) )

        print( "    %-30s %6u %11u %9u %8u" % ( "Total" if level >= 2 else str(len(self._testClients)),
                    self.getTotalNumPVs(), self.getTotalNumTsValues(),
                    self.getTotalNumMissed(), self.getTotalNumTimeouts() ) )

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

    def readFiles( self, dirTop, analyze = True, verbose = False ):
        if not os.path.isdir( dirTop ):
            print( "%s is not a directory!" % dirTop )
        for dirPath, dirs, files in os.walk( dirTop, topdown=True ):
            if verbose:
                (appPath, appName) = os.path.split( dirPath )
                if os.path.split(appPath)[1] == "clients":
                    print( "Processing client %s ..." % appName )
            for fileName in files:
                filePath = os.path.join( dirPath, fileName )
                stressTestFile = None
                if fileName.endswith( '.pvget' ):
                    stressTestFile = stressTestFilePVGet( filePath )
                elif fileName.endswith( 'pvCapture' ):
                    stressTestFile = stressTestFilePVCapture( filePath )
                #elif fileName.endswith( '.log' ):
                    # readLogFile( fileName )
                #elif fileName.endswith( '.list' ):
                #   continue
                #elif fileName.endswith( '.cfg' ):
                #   continue
                #elif fileName.endswith( '.info' ):
                    # readInfoFile( fileName )

                if not stressTestFile:
                    continue
                self._testFiles[filePath] = stressTestFile
                ( testName, hostName, appType, appName, pvName ) =  pathToTestAttr( filePath )
                if appType == "client":
                    client = self.getClient( appName, hostName )
                    client.addTestFile( pvName, stressTestFile )

        if analyze:
            self.analyze()
        return

