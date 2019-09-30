#!/bin/env python3

import argparse
import logging
import json
import os
import sys
import textwrap
import time
import pdb
import pprint

#from functools import partial
from p4p.client.thread import Context
from p4p.client.raw import Disconnected, RemoteError, Cancelled, Finished, LazyRepr
from threading import Lock
import p4p.nt.scalar

_log	= logging.getLogger(__name__)

EPICS2UNIX_EPOCH = 631152000.0

class pvGetClient(object):
    def __init__( self, pvName, provider='pva', verbose=False, checkPriorCount=False ):
        self._lock = Lock()
        self._pvName = pvName
        self._history = {}
        self._priorValue = None
        self._noConnectionYet = True
        self._verbose = verbose
        self._checkPriorCount = checkPriorCount
        self._ctxt = Context( provider )
        self._S = self._ctxt.monitor( pvName, self.callback, notify_disconnect=True )

    def __del__( self ):
        if self._ctxt is not None:
            self._ctxt.close()
            self._ctxt = None

    def pvName( self ):
        return self._pvName

    def callback( self, cbData ):
        pvName = self._pvName
        if isinstance( cbData, (RemoteError, Disconnected, Cancelled)):
            if self._noConnectionYet and isinstance( cbData, Disconnected ):
                return
            print( '%s: %s' % ( pvName, cbData ) )
            return

        self._noConnectionYet = False
        pvValue = cbData

        #pdb.set_trace()
        # Make sure we have a raw_stamp
        raw_stamp = None
        if hasattr( pvValue, 'raw_stamp' ):
            raw_stamp = pvValue.raw_stamp 
        elif isinstance( pvValue, dict ):
            if 'raw_stamp' in pvValue:
                raw_stamp = pvValue[ 'raw_stamp' ]
            if 'timestamp' in pvValue:
                raw_stamp = pvValue[ 'timestamp' ] 
            if 'timeStamp' in pvValue:
                raw_stamp = pvValue[ 'timeStamp' ] 

        if not raw_stamp or raw_stamp[0]:
            curTime = time.time()
            raw_stamp = ( int(curTime), int((curTime - int(curTime)) * 1e9) )

        if isinstance( pvValue, p4p.nt.scalar.ntwrappercommon ):
            return self.saveNtScalar( pvName, raw_stamp, pvValue )

        if isinstance( pvValue, p4p.wrapper.Value ):
            if self._verbose:
                print( '%s: ID=%s, type=%s' % ( pvName, pvValue.getID(), type(pvValue) ) )

            pvType = pvValue.type()
            if 'timeStamp' in pvValue:
                fieldTs = (	pvValue['timeStamp.secondsPastEpoch'],
                            pvValue['timeStamp.nanoseconds'] )
                if fieldTs[0]:
                    raw_stamp = fieldTs

            if pvValue.getID().startswith( 'epics:nt/NTTable:' ):
                tableValue	= pvValue['value']
                tableType	= pvType['value']
                S, id, tableFields = tableType.aspy()
                assert S == 'S'
                assert id == 'structure'
                tableItems = tableValue.items()
                nCols = len(tableItems)
                nRows = len(tableItems[0][1])
                if self._verbose:
                    print( "%s NTTable: nRows=%d, nCols=%d\n%s" % ( pvName, nRows, nCols, tableItems ) )
                for row in range( nRows ):
                    # Build up fullName
                    fullName = pvName
                    for col in range( nCols ):
                        spec = tableFields[col][1]
                        if spec == 'as':
                            fullName += '.' + tableItems[col][1][row]
                        elif spec != 'av' and spec != 'aU' and spec != 'aS':
                            self.saveValue( fullName + '.' + tableFields[col][0], raw_stamp, tableItems[col][1][row] )
                return

            # This method works fpr p2p/Stats and potentially other
            # simple PVStruct based PVs.
            #if pvValue.getID() == 'epics:p2p/Stats:1.0':
            for fieldName in pvValue.keys():
                pvField = pvValue[fieldName]
                if 'timeStamp' in pvField:
                    fieldTs = ( pvField['timeStamp.secondsPastEpoch'], pvField['timeStamp.nanoseconds'] )
                    if fieldTs[0]:
                        raw_stamp = fieldTs
                fullName = pvName + '.' + fieldName
                if isinstance( pvField, p4p.nt.scalar.ntwrappercommon ):
                    return self.saveNtScalar( fullName, raw_stamp, pvField['value'] )
                elif pvField.getID().startswith( 'epics:nt/NTScalar:' ):
                    return self.saveValue( fullName, raw_stamp, pvField['value'] )

        # TODO: Handle other nt types

    def saveNtScalar( self, pvName, raw_stamp, pvValue ):
        if self._verbose:
            print( '%s: ID=%s, type=%s' % ( pvName, pvValue.getID(), type(pvValue) ) )

        if self._checkPriorCount:
            newValue = int(pvValue)
            if self._priorValue is not None:
                # Check for missed count
                expectedValue = self._priorValue + 1
                if expectedValue != newValue:
                    print( '%s: missed %d counts!' % ( pvName, newValue - expectedValue ) )
            self._priorValue	= newValue

        # Save value
        self.saveValue( pvName, raw_stamp, pvValue )
        return

    def saveValue( self, pvName, raw_stamp, value ):
        # assert pvValue.type() == Scalar:
        if pvName not in self._history:
            self._history[ pvName ] = []
        self._history[ pvName ] += [ [ raw_stamp, value ] ]

        strTimeStamp = time.strftime( "%Y-%m-%d %H:%M:%S", time.localtime( raw_stamp[0] ) )
        print( '%s %s.%03d %s' % ( pvName, strTimeStamp, float(raw_stamp[1])/1e6, float(value) ) )

        if self._verbose:
            print( '%s: value raw_stamp = %s' % ( pvName, raw_stamp ) )
            print( '%s: Num values = %d' % ( pvName, len(self._history[pvName]) ) )

    def writeValues( self, dirName ):
        if not os.path.isdir( dirName ):
            os.mkdir( dirName )
        for pvName in self._history:
            saveFile = os.path.join( dirName, pvName + '.pvget' )
            try:
                pvHistory = self._history[pvName]
                with open( saveFile, "w" ) as f:
                    if self._verbose or True:
                        print( "Writing %d values to %s ..." % ( len(pvHistory), saveFile ) )
                    # Skipping json.dump so it matches similar, but more compact, stressTestClient pvCapture output
                    #json.dump( pvHistory, f, indent=4 )
                    #continue
                    f.write( '[\n' )
                    for tsVal in pvHistory[0:-1]:
                        f.write( "\t[ [ %d, %d ], %d ],\n" % ( tsVal[0][0], tsVal[0][1], tsVal[1] ) )
                    f.write( "\t[ [ %d, %d ], %d ]\n" % ( tsVal[0][0], tsVal[0][1], tsVal[1] ) )
                    f.write( ']\n' )
            except BaseException as e:
                print( "Error: %s" % e )
                print( "Unable to write values to %s" % saveFile )

    def closeSubscription( self ):
        if self._S is not None:
            print( "Closing subscription to %s" % self._pvName )
            self._S.close()
            self._S = None

    def __exit__( self ):
        self.closeSubscription()

def process_options(argv):
    if argv is None:
        argv = sys.argv[1:]
    description = 'pvGet.py is a python test program for monitoring PVs via PVAccess.\n'
    epilog_fmt =  '\nExamples:\n' \
            + 'pvGet.py  TEST:01:AnalogIn0 TEST:02:Dig1\n'
    epilog = textwrap.dedent( epilog_fmt )
    parser = argparse.ArgumentParser( description=description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog )
    parser.add_argument( 'pvNames', metavar='PV', nargs='+',
                        help='EPICS PVA pvNames Example: TEST:01:AnalogIn0', default=[] )
    parser.add_argument( '-m', '--monitor',  action='store', default=True, help='Stay connected and monitor updates.' )
    parser.add_argument( '-p', '--provider', action='store', default='pva', help='PV provider protocol, default is pva.' )
    parser.add_argument( '-f', '--input_file_path', action='store', help='Read list of pvNames from this file.' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )

    options = parser.parse_args( )

    return options 

def main(argv=None):
    options = process_options(argv)

    clients = []
    for pvName in options.pvNames:
        clients.append( pvGetClient( pvName, provider=options.provider, verbose=options.verbose ) )

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass

    for client in clients:
        client.closeSubscription()
    for client in clients:
        client.writeValues('/tmp/TODO-add-dir-arg')
    time.sleep(1)

if __name__ == '__main__':
    status = main()
    sys.exit(status)
