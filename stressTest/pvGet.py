#!/bin/env python3

import argparse
import logging
import json
import os
import sys
import textwrap
import time
import pdb

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
            print( '%s: %s' % ( pvName, cbData ) )
            return

        pvValue = cbData

        # Make sure we have a raw_stamp
        if hasattr( pvValue, 'raw_stamp' ):
            raw_stamp = pvValue.raw_stamp 
        else:
            curTime = time.time()
            raw_stamp = (	int(curTime) - EPICS2UNIX_EPOCH + EPICS2UNIX_EPOCH,
                            (curTime - int(curTime)) * 1e9  )

        if isinstance( pvValue, p4p.nt.scalar.ntwrappercommon ):
            if self._verbose:
                print( '%s type: %s' % ( pvName, type(pvValue) ) )

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

        #pdb.set_trace()
        if isinstance( pvValue, p4p.wrapper.Value ):
            pvType = pvValue.type()
            if 'timeStamp' in pvValue:
                raw_stamp = (	pvValue['timeStamp.secondsPastEpoch'],
                                pvValue['timeStamp.nanoseconds'] )
            #if pvValue.getID().startswith( 'epics:nt/NTTable:' ):
            #	Need to loop through table rows
            #	fullName = pvName + '.' + col[0].name + '.' + col[1].name
            #	value = col[2].value
            #else:
            #if pvValue.getID() == 'epics:p2p/Stats:1.0':
            for fieldName in pvValue.keys():
                pvField = pvValue[fieldName]
                if 'timeStamp' in pvField:
                    fieldTs = ( pvField['timeStamp.secondsPastEpoch'], pvField['timeStamp.nanoseconds'] )
                    if fieldTs[0]:
                        raw_stamp = fieldTs
                fullName = pvName + '.' + fieldName
                if pvField.getID().startswith( 'epics:nt/NTScalar:' ):
                    self.saveValue( pvName + '.' + fieldName, raw_stamp, pvField['value'] )

        # TODO: Handle other nt types

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
            + 'pvGet.py -p TEST:01:AnalogIn0\n'
    epilog = textwrap.dedent( epilog_fmt )
    parser = argparse.ArgumentParser( description=description, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog )
    parser.add_argument( '-P', '--pvName',   dest='pvNames', action='append', \
                        help='EPICS PVA pvNames Example: TEST:01:AnalogIn0', default=[] )
    parser.add_argument( '-p', '--provider', action='store', default='pva', help='PV provider protocol, default is pva' )
    parser.add_argument( '-f', '--input_file_path', action='store', help='Read list of pvNames from this file' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )

    options = parser.parse_args( )

    return options 

def main(argv=None):
    options = process_options(argv)

    if len(options.pvNames) == 0:
        options.pvNames = [ 'PVA:GW:TEST:01:Count00', 'PVA:GW:TEST:02:Count00', 'PVA:GW:TEST:02:Count01' ]
    clients = []
    #_ctxt	= Context('pva')
    #pvValue = _ctxt.get( pvNames[0] )
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
        client.writeValues('/tmp/fastClient')
    time.sleep(1)

if __name__ == '__main__':
    status = main()
    sys.exit(status)
