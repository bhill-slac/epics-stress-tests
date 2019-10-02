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
import threading

#from functools import partial
from p4p.client.thread import Context
from p4p.client.raw import Disconnected, RemoteError, Cancelled, Finished, LazyRepr
from p4p.client.raw import Disconnected, RemoteError, Cancelled, Finished, LazyRepr
from threading import Lock
import p4p.nt.scalar

try:
    from Queue import Queue, Full, Empty
except ImportError:
    from queue import Queue, Full, Empty

_log	= logging.getLogger(__name__)

#EPICS2UNIX_EPOCH = 631152000.0


class pvGetClient(object):
    def __init__( self, pvName, monitor='False', provider='pva', timeout=5.0, repeat=1.0, throw=False, verbose=False, checkPriorCount=False ):
        self._lock = Lock()
        self._pvName = pvName
        self._history = {}
        self._priorValue = None
        self._Q = Queue()
        self._S = None
        self._T = None
        self._Op = None
        self._noConnectionYet = True
        self._shutDown = False
        self._throw = throw
        self._repeat = repeat
        self._timeout = timeout
        self._verbose = verbose
        self._checkPriorCount = checkPriorCount
        self._ctxt = Context( provider )
        self._pvGetDone = threading.Event()
        self._pvGetPending = threading.Condition()
        self._T = threading.Thread( target=self.pvGetTimeoutLoop, args=(self._timeout,self._throw,self._verbose) )
        self._T.start()

    def __del__( self ):
        if self._ctxt is not None:
            self._ctxt.close()
            self._ctxt = None

    def is_alive( self ):
        if not self._T:
            return False
        return self._T.is_alive()

    def pvMonitor( self ):
        # Monitor is is easy as p4p provides it.
        self._S = self._ctxt.monitor( self._pvName, self.callback, notify_disconnect=True )
        # Above code does this:
        # R = Subscription( self._ctxt, self._pvName, self.callback, notify_disconnect=True )
        # R._S = super(Context, self).monitor( name, R._event, request )
        # self._S = R

    def pvGetInitiate( self, timeout=5.0, throw=False, verbose=True ):
        #pdb.set_trace()
        # This code block does a synchronous get()
        #return self._ctxt.get( self._pvName, self.callback )

        # Initiate async non-blocking pvGet using a ClientOperation.
        # self.pvGetCallback() handles the response and places it on self._Q
        raw_get = super( Context, self._ctxt ).get
        with self._pvGetPending:
            try:
                assert self._Op is None
                self._Op = raw_get( self._pvName, self.pvGetCallback )
                print( "%s: Called raw_get, notify _pvGetPending" % self._pvName )
                self._pvGetPending.notify()
            except:
                raise
        print( "%s: Exiting pvGetInitiate" % self._pvName )
        return

    def pvGetCallback( self, cbData ):
        print( "%s: Entering pvGetCallback" % self._pvName )
        result = self.callback( cbData )
        #pdb.set_trace()
        assert self._Q
        try:
            self._Q.put_nowait( result )
            print( "%s: Added result to queue. %d on queue." % ( self._pvName, self._Q.qsize() ) )
        except:
            print( "pvGetCallback %s: Error queuing result" % self._pvName )
        return

    def handleResult( self ):
        # Get pvGet result from self._Q
        result = False
        try:
            print( "%s: handleResult: Getting result from Q." % ( self._pvName ) )
            result = self._Q.get( timeout=self._timeout )
            print( "%s: handleResult: Got result from Q: %s" % ( self._pvName, result ) )
        except Empty:
            print( "%s: handleResult timeout after %s sec!" % ( self._pvName, self._timeout  ) )
            _log.debug( '%s: timeout after %s sec', self._pvName, self._timeout )
            if self._throw:
                raise TimeoutError();
        finally:
            with self._lock:
                if self._Op:
                    if self._verbose:
                        print( '%s: Closing ClientOperation ...' % ( self._pvName ) )
                    self._Op.close()
                    self._Op = None
        if isinstance(result, Exception):
            print( '%s result is an exception: %s' % ( self._pvName, result ) )
            if self._throw:
                raise result
            return False

        print( '%s result: %s' % ( self._pvName, result ) )
        #return result
        return True

    def pvGetTimeoutLoop( self, timeout=5.0, throw=False, verbose=True ):
        print( "%s: Entering pvGetTimeoutLoop" % self._pvName )
        status = False
        while not self._shutDown:
            with self._pvGetPending:
                # Wait for something to do.
                print( "%s: pvGetTimeoutLoop calling wait_for." % ( self._pvName ) )
                status = self._pvGetPending.wait_for( self.handleResult, timeout=timeout )
                print( "%s: pvGetTimeoutLoop woke from wait_for: status %s" % ( self._pvName, status ) )
            if not status:
                break
                    # pvGet timeout

            if self._shutDown:
                break

            if self._repeat is None:
                # Exit thread loop
                self._shutDown = True
            if self._shutDown:
                break
            print( "%s: pvGetTimeoutLoop sleeping for %s" % ( self._pvName, self._repeat ) )
            time.sleep( self._repeat )
            print( "%s: pvGetTimeoutLoop calling for pvGetInitiate." % ( self._pvName ) )
            self.pvGetInitiate()

        print( "%s: Exiting pvGetTimeoutLoop" % self._pvName )
        return

    def pvName( self ):
        return self._pvName

    def callback( self, cbData ):
        pvName = self._pvName
        if isinstance( cbData, (RemoteError, Disconnected, Cancelled)):
            if self._noConnectionYet and isinstance( cbData, Disconnected ):
                return cbData
            print( '%s: %s' % ( pvName, cbData ) )
            return cbData

        print( "%s: Entering callback" % self._pvName )
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
            self.saveNtScalar( pvName, raw_stamp, pvValue )
            return cbData

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
                return cbData

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
        return cbData

    def saveNtScalar( self, pvName, raw_stamp, pvValue ):
        if self._verbose:
            print( '%s: type=%s' % ( pvName, type(pvValue) ) )

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
                    if len(pvHistory) > 1:
                        for tsVal in pvHistory[0:-1]:
                            f.write( "\t[ [ %d, %d ], %d ],\n" % ( tsVal[0][0], tsVal[0][1], tsVal[1] ) )
                    if len(pvHistory) > 0:
                        # Write last value
                        tsVal = pvHistory[-1]
                        f.write( "\t[ [ %d, %d ], %d ],\n" % ( tsVal[0][0], tsVal[0][1], tsVal[1] ) )
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
    parser.add_argument( '-f', '--input_file_path', action='store', help='Read list of pvNames from this file.' )
    parser.add_argument( '-m', '--monitor',  action='store', help='Stay connected and monitor updates.' )
    parser.add_argument( '-p', '--provider', action='store', default='pva', help='PV provider protocol, default is pva.' )
    parser.add_argument( '-r', '--repeat', action='store', type=float, help='Repeat delay.' )
    parser.add_argument( '-t', '--timeout', action='store', type=float, default='5.0', help='Timeout in sec.' )
    parser.add_argument( '-v', '--verbose',  action="store_true", help='show more verbose output.' )

    options = parser.parse_args( )

    return options 

def main(argv=None):
    options = process_options(argv)

    clients = []
    for pvName in options.pvNames:
        clients.append( pvGetClient( pvName, monitor=options.monitor,
                            provider=options.provider, repeat=options.repeat,
                            verbose=options.verbose ) )

    for client in clients:
        if options.monitor:
            client.pvMonitor()
        else:
            client.pvGetInitiate()

    try:
        while True:
            if options.monitor:
                time.sleep(5)
                continue
            else:
                activeClients = False
                for client in clients:
                    if client.is_alive():
                        activeClients = True
                    else:
                        print( "Client %s dead." % client._pvName )
                if not activeClients:
                    break
                time.sleep( 1 )

    except KeyboardInterrupt:
        pass

    if options.verbose:
        print( "Done.  Closing all client subscriptions ..." )
    for client in clients:
        client.closeSubscription()
    for client in clients:
        client.writeValues('/tmp/TODO-add-dir-arg')
    time.sleep(1)

if __name__ == '__main__':
    status = main()
    sys.exit(status)
