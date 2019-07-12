#!/usr/bin/env python2
import datetime
import fileinput
import io
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

def fixPVCaptureFile( filePath ):
    fileLines = []
    with open( filePath, mode='r' ) as fd:
        for line in fd:
            fileLines.append( line )
    if len(fileLines) < 1:
        return
    lastLine = fileLines[-1]
    if lastLine.endswith(',\n'):
        fileLines[-1] = lastLine[0:-2] + "\n"
        fileLines.append( "]\n" )

        print( "Corrupted file: %s" % ( filePath + ".bak" ) )
        #print( "Saving  corrupted  file as: %s\n" % ( filePath + ".bak" ) )
        #print( "Successfully restored file: %s\n" % ( filePath ) )
        os.rename( filePath, filePath + ".bak" )
        with open( filePath, mode="w" ) as fw:
            for line in fileLines:
                fw.write( line )
            fw.close()
            print( "Restored  file: %s" % ( filePath ) )
            #print( "Successfully restored file: %s\n" % ( filePath ) )

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
        f.close()
        # Try to fix the most common json errors in PVCapture files
        fixPVCaptureFile( filePath )
        try:
            f2 = open( filePath )
            contents = json.load( f2 )
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

    pvgetRawTsEx  = r"Get: \S{3}\s+(.*)$"
    pvgetTsRegEx  = re.compile( pvgetRawTsEx )
    #pvgetRawEx = r"\S*\s*(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d+\.?\d*)\s\+(\d+\.?\d*)"
    epicsEpoch  = datetime.datetime( 1990, 1, 1 )
    try:
        contents = [[]]
        pvName =  os.path.splitext( os.path.split[1] )
        with open(filePath, 'r') as f:
            for line in f:
                if line.startswith( 'Timeout' ):
                    contents[pvName] += [ TS_VALUE_TIMEOUT ]
                    continue
                match = re.match( r"Read\s+\d+", line )
                if match:
                    # TODO: pvgetArray needs to track # of bytes read w/ ts
                    continue

                # Some PVA pv's just provide one timestamp on Get: line
                # Get: AAA bbb dd HH:MM:SS zzz YYYY
                match = pvgetRegTsEx.match( line )
                if match:
                    timestamp = datetime.strptime( match.group(1), "%b %d %H:%M:%S %z %Y" )
                    if timestamp:
                        lastTs = timestamp
                    continue

                # TODO: Use regex and allow pvName to be optional
                # PV:NAME  YYYY-MM-DD HH:MM:SS.FFF   FLOAT
                match = pvgetRegEx.match( line )
                if match:
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
                    if match.group(1):
                        pvName = match.group(1)
                    contents[pvName] += [ tsValue ]
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
            #tsValueList = {}
            self._tsTimeouts = {}
            self._numTimeouts = 0
            priorTs = None
            contents = readpvgetFile( pathTopToFile )
            #for pvName in contents:
            #for tsValue in contents[pvName]:
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
        self.processPVGetArrayFile( pathTopToFile )
    def getFileType( self ):
        return "pvgetarray"

    def processPVGetArrayFile( self, pathTopToFile ):
        try:
            #tsValueList = {}
            self._tsTimeouts = {}
            self._numTimeouts = 0
            priorTs = None
            return
            contents = readpvgetArrayFile( pathTopToFile )
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

