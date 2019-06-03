#!/usr/bin/env python3
class stressTestFile:
    def __init__( self, pathTopToFile ):
        ( self._filePath, self._fileName ) = os.path.split( pathTopToFile )
        self._numLines = None
        self._numTsValues = None

    def getFileName( self ):
        return self._FilePath
    def getFilePath( self ):
        return self._FilePath
    def getFileType( self ):
        return None
    def getNumLines( self ):
        return self._numLines
    def getNumTsValues( self ):
        return self._numTsValues

class stressTestFilePVGet( stressTestFile ):
    def __init__( self ):
        super( stressTestFile, self ).__init__( fileName, filePath )
        self._numTsValue = None
    def getFileType( self ):
        return "pvget"

class stressTestFilePVGetArray( stressTestFile ):
    def __init__( self ):
        super( stressTestFile, self ).__init__( fileName, filePath )
        self._numTsValue = None
    def getFileType( self ):
        return "pvgetarray"

class stressTestFileGWStats( stressTestFile ):
    def __init__( self ):
        super( stressTestFile, self ).__init__( fileName, filePath )
        self._numTsValue = None
    def getFileType( self ):
        return "gwstats"

