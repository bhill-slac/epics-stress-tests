#!/usr/bin/env python2
import datetime
import os
import re
import json

TS_VALUE_TIMEOUT = [ [ None, None ], None ]

class InvalidStressTestCaptureFile( Exception ):
    pass

def fileGetNumLines( filePath ):
    numLines = 0
    with open(filePath, 'r') as f:
        for line in f:
            numLines += 1
    return numLines

def readPVCaptureFile( filePath ):
    '''Capture files should follow json syntax and contain
    a list of tsPV values.
    Each tsPV is a list of timestamp, value.
    Each timestamp is a list of EPICS secPastEpoch, nsec.
    Ex.
    [
        [ [ 1559217327, 738206558], 8349 ],
        [ [ 1559217327, 744054279], 8350 ]
    ]
    '''
    try:
        f = open( filePath )
        contents = json.load( f )
        return contents
    except BaseException as e:
        raise InvalidStressTestCaptureFile( "readPVCaptureFile Error: %s: %s" % ( filePath, e ) )

def readpvgetFile( filePath ):
    '''pvget files are a temporary hack while pvGet app is not ready.
    Uses vanila pvget command line output redirected to file.
    Expected syntax:
    PV:NAME YYYY-MM-DD HH:MM:SS.SSS  VALUE
    or
    Timeout
    PV:NAME

    Note that a timeout generates 2 lines.
    
    Returns: list of tsPV
    Each tsPV is a list of timestamp, value.
    Each timestamp is a list of EPICS secPastEpoch, nsec.
    Timeout instances set tsPV to [ [ None, None ], None ]
    TODO: Convert timestamp from [sec,nsec] to float in these file readers
    and return a list of tsValues [ floatTs, floatValue ]
    Ex.
    [
        [ [ 1559217327, 738206558], 8349 ],
        [ [ None, None], None ],
        [ [ 1559217327, 744054279], 8350 ]
    ]

    TODO: Rework run_pvget.sh to suppress redundant pvName
    and generate more precision in the timestamp seconds.
    Parser could handle either by allowing pvName field
    to be optional.  Lines w/o timeout or tsValue are ignored. 
    '''
    pvNameRawEx = r"(\S*)"
    dateRawEx   = r"(\d{4}-\d{2}-\d{2})"
    floatRawEx  = r"(\d+\.?\d*)"
    timeRawEx   = r"(\d{2}:\d{2}:\d+\.?\d*)"
    pvgetRawEx  = pvNameRawEx
    pvgetRawEx  = pvgetRawEx + r"\s+" + dateRawEx
    pvgetRawEx  = pvgetRawEx + r"\s+" + timeRawEx
    pvgetRawEx  = pvgetRawEx + r"\s+" + floatRawEx
    pvgetRegEx  = re.compile( pvgetRawEx )
    #pvgetRawEx = r"\S*\s*(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d+\.?\d*)\s\+(\d+\.?\d*)"
    epicsEpoch  = datetime.datetime( 1990, 1, 1 )
    try:
        contents = []
        with open(filePath, 'r') as f:
            for line in f:
                if line.startswith( 'Timeout' ):
                    contents += [ TS_VALUE_TIMEOUT ]
                    continue
                match = re.match( r"Read\s+\d+", line )
                if match:
                    # TODO: Track # of bytes read w/ ts
                    continue
                # Use regex and allow pvName to be optional
                match = pvgetRegEx.match( line )
                if not match:
                    continue
                try:
                    # TODO: 3.7 adds datetime.fromisoformat
                    ( YY, MM, DD ) = match.group(2).split('-')
                    ( hh, mm, ss ) = match.group(3).split(':')
                    ( YY, MM, DD ) = ( int(YY), int(MM), int(DD) )
                    ( hh, mm, ss ) = ( int(hh), int(mm), float(ss) )
                    ( ss, us ) = ( int(ss), int(ss/100000) )
                    timestamp = datetime.datetime( YY, MM, DD, hh, mm, ss, us )
                    value     = float(match.group(4))
                    deltaEpoch = (timestamp - epicsEpoch)
                    deltaUsec = deltaEpoch / datetime.timedelta(microseconds=1)
                    tsEpoch = deltaUsec / 1000.0
                    tsEpochSec = int(tsEpoch)
                    nSec = int( (tsEpoch - tsEpochSec) * 1e9 )
                    tsValue = [ [ tsEpochSec, nSec ], value ]
                    contents += [ tsValue ]
                    continue

                except BaseException as e:
                    print( "readpvgetFile Error: %s: %s" % ( filePath, e ) )
                    continue
        return contents
    except BaseException as e:
        raise InvalidStressTestCaptureFile( "readpvgetFile Error: %s: %s" % ( filePath, e ) )

def readPVGetFile( filePath ):
    '''Get files should follow json syntax and contain
    a list of tsPV values.
    Each tsPV is a list of timestamp, value.
    Each timestamp is a list of EPICS secPastEpoch, nsec.
    Ex.
    [
        [ [ 1559217327, 738206558], 8349 ],
        [ [ 1559217327, 744054279], 8350 ]
    ]
    '''
    try:
        f = open( filePath )
        contents = json.load( f )
        return contents
    except BaseException as e:
        raise InvalidStressTestCaptureFile( "readPVGetFile Error: %s: %s" % ( filePath, e ) )

class stressTestFile:
    def __init__( self, pathTopToFile ):
        ( self._filePath, self._fileName ) = os.path.split( pathTopToFile )
        self._numLines = fileGetNumLines( pathTopToFile )
        self._tsValues = {}
        self._tsTimeouts = {}
        self._numTimeouts = 0

    def getFileName( self ):
        return self._FilePath
    def getFilePath( self ):
        return self._FilePath
    def getFileType( self ):
        return None
    def getNumLines( self ):
        return self._numLines
    def getNumTsValues( self ):
        return len(self._tsValues)
    def getTsValues( self ):
        return self._tsValues
    def getNumTimeouts( self ):
        return self._numTimeouts
    def getTsTimeouts( self ):
        return self._tsTimeouts

class stressTestFilePVGet( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super().__init__( pathTopToFile )
        self.processPVGetFile( pathTopToFile )

    def getFileType( self ):
        return "pvget"

    def processPVGetFile( self, pathTopToFile ):
        try:
            tsValueList = {}
            self._tsTimeouts = {}
            self._numTimeouts = 0
            priorTs = None
            contents = readpvgetFile( pathTopToFile )
            for tsValue in contents:
                timeStamp = tsValue[0]  # timeStamp should be [ secPastEpoch, nsec ]
                value = tsValue[1]
                if value is None:
                    self._numTimeouts = self._numTimeouts + 1
                    if timeStamp is None or timeStamp[0] is None or timeStamp[1] is None:
                        # Hack till I get timestamped timeouts in *.pvget
                        if priorTs is not None:
                            timeStamp = [ priorTs[0] + 2, priorTs[1] + 1 ]

                if timeStamp[0] is not None and timeStamp[1] is not None:
                    self._tsValues[ timeStamp[0] + timeStamp[1]*1e-9 ] = value
                    priorTs = timeStamp

        except InvalidStressTestCaptureFile as e:
            print( e )
            raise
            #pass
        except BaseException as e:
            print( "processPVGetFile Error: %s: %s" % ( pathTopToFile, e ) )
            raise
            #pass

class stressTestFilePVCapture( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super().__init__( pathTopToFile )
        self.processPVCaptureFile( pathTopToFile )

    def processPVCaptureFile( self, pathTopToFile ):
        try:
            tsValueList = readPVCaptureFile( pathTopToFile )
            # super(stressTestFile, self).getTsValues( self ) = {}
            # self._tsValues = {}
            for tsValue in tsValueList:
                timeStamp = tsValue[0]  # timeStamp should be [ secPastEpoch, nsec ]
                value = tsValue[1]
                self._tsValues[ timeStamp[0] + timeStamp[1]*1e-9 ] = value

        except InvalidStressTestCaptureFile as e:
            print( e )
            pass
        except BaseException as e:
            print( "processPVCaptureFile Error: %s: %s" % ( pathTopToFile, e ) )
            pass

    def getFileType( self ):
        return "pvCapture"


# Example code
#class LoggingDict(SomeOtherMapping):            # new base class
#    def __setitem__(self, key, value):
#        logging.info('Settingto %r' % (key, value))
#        super().__setitem__(key, value)         # no change needed

class stressTestFilePVGetArray( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super( stressTestFile, self ).__init__( pathTopToFile )
    def getFileType( self ):
        return "pvgetarray"
    #def getTsValues( self ):
    #   return super( stressTestFile, self ).getTsValues()

class stressTestFileGWStats( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super( stressTestFile, self ).__init__( pathTopToFile )
    def getFileType( self ):
        return "gwstats"


class stressTestFileGWStats( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super( stressTestFile, self ).__init__( pathTopToFile )
    def getFileType( self ):
        return "gwstats"

