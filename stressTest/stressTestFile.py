#!/usr/bin/env python2
import os
import json

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

class stressTestFile:
    def __init__( self, pathTopToFile ):
        ( self._filePath, self._fileName ) = os.path.split( pathTopToFile )
        self._numLines = fileGetNumLines( pathTopToFile )
        self._numTsValues = None
        self._tsValues = {}

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

class stressTestFilePVGet( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super().__init__( pathTopToFile )

    def getFileType( self ):
        return "pvget"

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
        #self._numTsValue = None
    def getFileType( self ):
        return "pvgetarray"
    #def getTsValues( self ):
    #   return super( stressTestFile, self ).getTsValues()

class stressTestFileGWStats( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super( stressTestFile, self ).__init__( pathTopToFile )
        #self._numTsValue = None
    def getFileType( self ):
        return "gwstats"


class stressTestFileGWStats( stressTestFile ):
    def __init__( self, pathTopToFile ):
        super( stressTestFile, self ).__init__( pathTopToFile )
        #self._numTsValue = None
    def getFileType( self ):
        return "gwstats"

