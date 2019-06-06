#!/usr/bin/env python3

class stressTestPV:
    def __init__( self, pvName ):
        self._pvName = pvName
        self._tsValues    = {}      # Dict of collected values,   keys are float timestamps
        self._tsRates     = {}      # Dict of collection rates,   keys are int secPastEpoch values
        self._tsMissRates = {}      # Dict of missed count rates, keys are int secPastEpoch values
        self._timeoutRates= {}      # Dict of timeout rates, keys are int secPastEpoch values
        self._numMissed   = 0       # Cumulative number of missed counts
        self._numTimeouts = 0       # Cumulative number of timeouts
        self._startTime   = None    # Earliest timestamp of all collected values
        self._endTime     = None    # Latest   timestamp of all collected values

    # Accessors
    def getName( self ):
        return self._pvName
    def getNumTsValues( self ):
        return len(self._tsValues)
    def getNumMissed( self ):
        return self._numMissed
    def getNumTimeouts( self ):
        return self._numTimeouts
    def getEndTime( self ):
        return self._endTime;
    def getStartTime( self ):
        return self._startTime;
    def getTsValues( self ):
        return self._tsValues
    def getTsRates( self ):
        return self._tsRates
    def getTsMissRates( self ):
        return self._tsMissRates
    def getTimeoutRates( self ):
        return self._timeoutRates

    def addTsValues( self, tsValues ):
        # TODO: check for more than one value for the same timestamp
        self._tsValues.update( tsValues )

    def addTsTimeouts( self, tsTimeouts ):
        self._tsTimeouts.update( tsTimeouts )

    # stressTestPV.analyze
    def analyze( self ):
        ( priorSec, priorValue ) = ( None, None )
        ( count, missed, timeouts ) = ( 0, 0, 0 )
        sec = None
        for timestamp in self._tsValues:
            sec = int(timestamp)
            if priorSec is None:
                self._endTime   = timestamp
                self._startTime = timestamp
                priorSec = sec - 1
            if sec != priorSec:
                if  self._endTime < sec:
                    self._endTime = sec
                self._tsRates[priorSec] = count
                self._tsMissRates[priorSec] = missed
                self._timeoutRates[priorSec] = timeouts
                self._numMissed += missed
                self._numTimeouts += timeouts
                ( count, missed, timeouts ) = ( 0, 0, 0 )
                # Advance priorSec, filling gaps w/ zeroes
                while True:
                    priorSec += 1
                    if priorSec >= sec:
                        break
                    self._tsRates[priorSec] = 0
                    self._tsMissRates[priorSec] = 0
                    self._timeoutRates[priorSec] = 0
                priorSec = sec
            count += 1
            value = self._tsValues[timestamp]
            if value is None:
                timeouts += 1
                continue
            if priorValue is not None:
                if priorValue + 1 != value:
                    # Keep track of miss incidents
                    #missed += 1
                    # or
                    # Keep track of how many we missed
                    missed += ( value - priorValue + 1 )
            priorValue = value

        if sec:
            self._tsRates[sec] = count
            self._tsMissRates[sec] = missed
            self._timeoutRates[sec] = timeouts

