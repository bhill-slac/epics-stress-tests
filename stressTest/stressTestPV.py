#!/usr/bin/env python3

class stressTestPV:
    def __init__( self, pvName ):
        self._pvName = pvName
        self._tsValues    = {}      # Dict of collected values,   keys are float timestamps
        self._tsRates     = {}      # Dict of collection rates,   keys are int secPastEpoch values
        self._tsMissRates = {}      # Dict of missed count rates, keys are int secPastEpoch values
        self._numMissed   = 0       # Cumulative number of missed counts
        self._startTime   = None    # Earliest timestamp of all collected values
        self._endTime     = None    # Latest   timestamp of all collected values

    # Accessors
    def getName( self ):
        return self._pvName
    def getNumTsValues( self ):
        return len(self._tsValues)
    def getNumMissed( self ):
        return self._numMissed
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

    def addTsValues( self, tsValues ):
        # TODO: check for more than one value for the same timestamp
        # TODO: check for out of order timestamps
        self._tsValues.update( tsValues )

    # stressTestPV.analyze
    def analyze( self ):
        ( priorSec, priorValue ) = ( None, None )
        ( missed, count ) = ( 0, 0 )
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
                self._numMissed += missed
                ( missed, count ) = ( 0, 0 )
                # Advance priorSec, filling gaps w/ zeroes
                while True:
                    priorSec += 1
                    if priorSec >= sec:
                        break
                    self._tsRates[priorSec] = 0
                    self._tsMissRates[priorSec] = 0
                priorSec = sec
            count += 1
            value = self._tsValues[timestamp]
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
            self._numMissed += missed

