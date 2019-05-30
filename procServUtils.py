######################################################################
#
# Exported API routines:
#
# check_status(host, port, id)
#     Check the health of an IOC, returning a dictionary with status,
#     pid, id, autorestart, and rdir.
#
# killProc(host, port)
#     Kill the IOC at the given location.
#
# restartProc(host, port)
#     Restart the IOC at the given location.
#
# rebootServer(host)
#     Attempt to reboot the specified host.
#
######################################################################


import telnetlib, string, datetime, os, time, fcntl, re, glob, subprocess, copy

#
# Defines
#

STATUS_INIT      = "INITIALIZE WAIT"
STATUS_NOCONNECT = "NOCONNECT"
STATUS_RUNNING   = "RUNNING"
STATUS_SHUTDOWN  = "SHUTDOWN"
STATUS_ERROR     = "ERROR"

#CONFIG_NORMAL    = 0
#CONFIG_ADDED     = 1
#CONFIG_DELETED   = 2

# messages expected from procServ
MSG_BANNER_END = b"server started at"
MSG_ISSHUTDOWN = b"is SHUT DOWN"
MSG_ISSHUTTING = b"is shutting down"
MSG_KILLED     = b"process was killed"
MSG_RESTART = b"new child"
MSG_PROMPT_OLD = b"\x0d\x0a[$>] "
MSG_PROMPT = b"\x0d\x0a> "
MSG_SPAWN = b"procServ: spawning daemon"
MSG_AUTORESTART_IS_ON = b"auto restart is ON"
MSG_AUTORESTART_TO_ON = b"auto restart to ON"
MSG_AUTORESTART_TO_OFF = b"auto restart to OFF"

######################################################################
#
# Telnet/Procserv Utilities
#

#
# Read and parse the connection information from a new procServ telnet connection.
# Returns a dictionary of information.
#
def readLogPortBanner(tn):
    try:
        response = tn.read_until(MSG_BANNER_END, 1)
    except:
        print( 'readLogPortBanner ERROR: timeout looking for \"%s\"' % MSG_BANNER_END )
        response = ""
    if not response.count(MSG_BANNER_END):
        return {'status'      : STATUS_ERROR,
                'pid'         : "-",
                'rid'          : "-",
                'autorestart' : False,
                'rdir'        : "/tmp" }
    if re.search(b'SHUT DOWN', response):
        tmpstatus = STATUS_SHUTDOWN
        pid = "-"
    else:
        tmpstatus = STATUS_RUNNING
        pid = re.search(b'@@@ Child \"(.*)\" PID: ([0-9]*)', response).group(2)
    match = re.search(b'@@@ Child \"(.*)\" start', response)
    gid = "-"
    if match:
        getid = match.group(1)
    match = re.search(b'@@@ Server startup directory: (.*)', response)
    dir = "/tmp"
    if match:
        dir   = match.group(1)
        if dir[-1] == '\r':
            dir = dir[:-1]
    if re.search(MSG_AUTORESTART_IS_ON, response):
        arst = True
    else:
        arst = False

    return {'status'      : tmpstatus,
            'pid'         : pid,
            'rid'         : getid,
            'autorestart' : arst,
            'rdir'        : dir  }

#
# Returns a dictionary with status information for a given host/port.
#
def check_status(host, port, id):
    try:
        tn = telnetlib.Telnet(host, port, 1)
    except:
        return {'status'      : STATUS_NOCONNECT,
                'rid'         : id,
                'pid'         : "-",
                'autorestart' : False,
                'rdir'        : "/tmp" }
    result = readLogPortBanner(tn)
    tn.close()
    return result

def openTelnet(host, port):
    connected = False
    telnetCount = 0
    while (not connected) and (telnetCount < 2):
        telnetCount += 1
        try:
            tn = telnetlib.Telnet(host, port, 1)
        except:
            #time.sleep(0.25)
            time.sleep(0.01)
            pass
        else:
            connected = True
    if connected:
        return tn
    else:
        return None

def killProc(host, port, verbose=False):
    if verbose or True:
        print( "Killing process on host %s, port %s ..." % (host, port) )

    # First, turn off autorestart!
    tn = openTelnet(host, port)
    if tn:
        try:
            statd = readLogPortBanner(tn)
        except:
            print( 'ERROR: killProc() failed to readLogPortBanner on %s port %s' % (host, port) )
            tn.close()
            return
        try:
            if verbose:
                print( 'killProc: %s port %s status is %s' % (host, port, statd['status']) )
            if statd['autorestart']:
                if verbose:
                    print( 'killProc: turning off autorestart on %s port %s' % (host, port) )
                # send ^T to toggle off auto restart.
                tn.write("\x14")
                # wait for toggled message
                r = tn.read_until(MSG_AUTORESTART_TO_OFF, 1)
                #time.sleep(0.25)
                time.sleep(0.01)
        except:
            print( 'ERROR: killProc() failed to turn off autorestart on %s port %s' % (host, port) )
            tn.close()
            return
        tn.close()
    else:
        print( 'ERROR: killProc() telnet to %s port %s failed' % (host, port) )
        return

    # Now, reconnect to actually kill it!
    tn = openTelnet(host, port)
    if tn:
        statd = readLogPortBanner(tn)
        if statd['status'] == STATUS_RUNNING:
            try:
                if verbose:
                    print( 'killProc: Sending Ctrl-C to %s port %s' % (host, port) )
                # send ^C to kill child process
                tn.write(b"\x03");
                # wait for shutting down message
                r = tn.read_until(MSG_ISSHUTTING, 1)
                #time.sleep(0.25)
                time.sleep(0.01)
                if r.count(MSG_ISSHUTTING):
                    statd['status'] = STATUS_SHUTDOWN
            except:
                pass

        if statd['status'] == STATUS_RUNNING:
            if verbose:
                print( 'Note: Ctrl-C failed to shutdown process on %s port %s' % (host, port) )
            try:
                if verbose:
                    print( 'killProc: Sending Ctrl-X to %s port %s' % (host, port) )
                # send ^X to kill child process
                tn.write(b"\x18");
                # wait for killed message
                r = tn.read_until(MSG_KILLED, 1)
                #time.sleep(0.25)
                time.sleep(0.01)
            except:
                print( 'ERROR: killProc() failed to kill process on %s port %s' % (host, port) )
                tn.close()
                return

        try:
            if verbose:
                print( 'killProc: Sending Ctrl-Q to %s port %s' % (host, port) )
            # send ^Q to kill procServ
            tn.write(b"\x11");
        except:
            print( 'ERROR: killProc() failed to kill procServ on %s port %s' % (host, port) )
            tn.close()
            return
        tn.close()
    else:
        print( 'ERROR: killProc() telnet to %s port %s failed' % (host, port) )

def restartProc(host, port):
    print( "Restarting process on host %s, port %s..." % (host, port) )
    tn = openTelnet(host, port)
    started = False
    if tn:
        statd = readLogPortBanner(tn)
        if statd['status'] == STATUS_RUNNING:
            try:
                # send ^X to kill child process
                tn.write("\x18");

                # wait for killed message
                r = tn.read_until(MSG_KILLED, 1)
                #time.sleep(0.25)
                time.sleep(0.01)
            except:
                pass # What do we do now?!?

        if not statd['autorestart']:
            # send ^R to restart child process
            tn.write("\x12");

        # wait for restart message
        r = tn.read_until(MSG_RESTART, 1)
        if not r.count(MSG_RESTART):
            print( 'ERROR: no restart message... ' )
        else:
            started = True

        tn.close()
    else:
        print( 'ERROR: restartProc() telnet to %s port %s failed' % (host, port) )

    return started

if __name__ == '__main__':
    status = 0
    try:
        response = check_status( 'localhost', 50002, 'ioc-tst-01' )
        print( response )
        killProc( 'localhost', 50002 )
    except BaseException as e:
        print( "Caught exception during main!" )
        print( e )
        pass
