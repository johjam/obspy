import os
import sys
import platform
import shutil
import subprocess
import copy
import tempfile
import glob
import fnmatch

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.widgets import MultiCursor as MplMultiCursor

from obspy.core import UTCDateTime
from obspy.seishub import Client


mpl.rc('figure.subplot', left=0.05, right=0.98, bottom=0.10, top=0.92,
       hspace=0.28)
mpl.rcParams['font.size'] = 10


COMMANDLINE_OPTIONS = [
        # XXX wasn't working as expected
        #[["--debug"], {'dest': "debug", 'action': "store_true",
        #        'default': False,
        #        'help': "Switch on Ipython debugging in case of exception"}],
        [["-t", "--time"], {'dest': "time", 'default': '2009-07-21T04:33:00',
                'help': "Starttime of seismogram to retrieve. It takes a "
                "string which UTCDateTime can convert. E.g. "
                "'2010-01-10T05:00:00'"}],
        [["-d", "--duration"], {'type': "float", 'dest': "duration",
                'default': 120, 'help': "Duration of seismogram in seconds"}],
        [["-i", "--ids"], {'dest': "ids",
                'default': 'BW.RJOB..EH*,BW.RMOA..EH*',
                'help': "Ids to retrieve, star for channel and wildcards for "
                "stations are allowed, e.g. 'BW.RJOB..EH*,BW.RM?*..EH*'"}],
        [["-s", "--servername"], {'dest': "servername", 'default': 'teide',
                'help': "Servername of the seishub server"}],
        [["-p", "--port"], {'type': "int", 'dest': "port", 'default': 8080,
                'help': "Port of the seishub server"}],
        [["--user"], {'dest': "user", 'default': 'obspyck',
                'help': "Username for seishub server"}],
        [["--password"], {'dest': "password", 'default': 'obspyck',
                'help': "Password for seishub server"}],
        [["--timeout"], {'dest': "timeout", 'type': "int", 'default': 10,
                'help': "Timeout for seishub server"}],
        [["-k", "--keys"], {'action': "store_true", 'dest': "keybindings",
                'default': False, 'help': "Show keybindings and quit"}],
        [["--lowpass"], {'type': "float", 'dest': "lowpass", 'default': 20.0,
                'help': "Frequency for Lowpass-Slider"}],
        [["--highpass"], {'type': "float", 'dest': "highpass", 'default': 1.0,
                'help': "Frequency for Highpass-Slider"}],
        [["--nozeromean"], {'action': "store_true", 'dest': "nozeromean",
                'default': False,
                'help': "Deactivate offset removal of traces"}],
        [["--pluginpath"], {'dest': "pluginpath",
                'default': "/baysoft/obspyck/",
                'help': "Path to local directory containing the folders with "
                "the files for the external programs. Large files/folders "
                "should only be linked in this directory as the contents are "
                "copied to a temporary directory (links are preserved)."}],
        [["--starttime-offset"], {'type': "float", 'dest': "starttime_offset",
                'default': 0.0, 'help': "Offset to add to specified starttime "
                "in seconds. Thus a time from an automatic picker can be used "
                "with a specified offset for the starttime. E.g. to request a "
                "waveform starting 30 seconds earlier than the specified time "
                "use -30."}],
        [["-m", "--merge"], {'type': "string", 'dest': "merge", 'default': "",
                'help': "After fetching the streams from seishub run a merge "
                "operation on every stream. If not done, streams with gaps "
                "and therefore more traces per channel get discarded.\nTwo "
                "methods are supported (see http://svn.geophysik.uni-muenchen"
                ".de/obspy/docs/packages/auto/obspy.core.trace.Trace.__add__"
                ".html for details)\n  \"safe\": overlaps are discarded "
                "completely\n  \"overwrite\": the second trace is used for "
                "overlapping parts of the trace"}],
        [["--arclink-ids"], {'dest': "arclink_ids",
                'default': '',
                'help': "Ids to retrieve via arclink, star for channel "
                "is allowed, e.g. 'BW.RJOB..EH*,BW.ROTZ..EH*'"}],
        [["--arclink-servername"], {'dest': "arclink_servername",
                'default': 'webdc.eu',
                'help': "Servername of the arclink server"}],
        [["--arclink-port"], {'type': "int", 'dest': "arclink_port",
                'default': 18001, 'help': "Port of the arclink server"}],
        [["--arclink-user"], {'dest': "arclink_user", 'default': 'Anonymous',
                'help': "Username for arclink server"}],
        [["--arclink-password"], {'dest': "arclink_password", 'default': '',
                'help': "Password for arclink server"}],
        [["--arclink-institution"], {'dest': "arclink_institution",
                'default': 'Anonymous',
                'help': "Password for arclink server"}],
        [["--arclink-timeout"], {'dest': "arclink_timeout", 'type': "int",
                'default': 20, 'help': "Timeout for arclink server"}],
        [["--fissures-ids"], {'dest': "fissures_ids",
                'default': '',
                'help': "Ids to retrieve via Fissures, star for component "
                "is allowed, e.g. 'GE.APE..BH*,GR.GRA1..BH*'"}],
        [["--fissures-network_dc"], {'dest': "fissures_network_dc",
                'default': ("/edu/iris/dmc", "IRIS_NetworkDC"),
                'help': "Tuple containing Fissures dns and NetworkDC name."}],
        [["--fissures-seismogram_dc"], {'dest': "fissures_seismogram_dc",
                'default': ("/edu/iris/dmc", "IRIS_DataCenter"),
                'help': "Tuple containing Fissures dns and DataCenter name."}],
        [["--fissures-name_service"], {'dest': "fissures_name_service",
                'default': "dmc.iris.washington.edu:6371/NameService",
                'help': "String containing the Fissures name service."}]]
PROGRAMS = {
        'nlloc': {'filenames': {'exe': "NLLoc", 'phases': "nlloc.obs",
                                'summary': "nlloc.hyp",
                                'scatter': "nlloc.scat"}},
        'hyp_2000': {'filenames': {'exe': "hyp2000",'control': "bay2000.inp",
                                   'phases': "hyp2000.pha",
                                   'stations': "stations.dat",
                                   'summary': "hypo.prt"}},
        'focmec': {'filenames': {'exe': "rfocmec", 'phases': "focmec.dat",
                                 'stdout': "focmec.stdout",
                                 'summary': "focmec.out"}},
        '3dloc': {'filenames': {'exe': "3dloc_pitsa", 'out': "3dloc-out",
                                'in': "3dloc-in"}}}
SEISMIC_PHASES = ['P', 'S']
PHASE_COLORS = {'P': "red", 'S': "blue", 'Psynth': "black", 'Ssynth': "black",
        'Mag': "green", 'PErr1': "red", 'PErr2': "red", 'SErr1': "blue",
        'SErr2': "blue"}
PHASE_LINESTYLES = {'P': "-", 'S': "-", 'Psynth': "--", 'Ssynth': "--",
        'PErr1': "-", 'PErr2': "-", 'SErr1': "-", 'SErr2': "-"}
PHASE_LINEHEIGHT_PERC = {'P': 1, 'S': 1, 'Psynth': 1, 'Ssynth': 1,
        'PErr1': 0.75, 'PErr2': 0.75, 'SErr1': 0.75, 'SErr2': 0.75}
KEY_FULLNAMES = {'P': "P pick", 'Psynth': "synthetic P pick",
        'PWeight': "P pick weight", 'PPol': "P pick polarity",
        'POnset': "P pick onset", 'PErr1': "left P error pick",
        'PErr2': "right P error pick", 'S': "S pick",
        'Ssynth': "synthetic S pick", 'SWeight': "S pick weight",
        'SPol': "S pick polarity", 'SOnset': "S pick onset",
        'SErr1': "left S error pick", 'SErr2': "right S error pick",
        'MagMin1': "Magnitude minimum estimation pick",
        'MagMax1': "Magnitude maximum estimation pick",
        'MagMin2': "Magnitude minimum estimation pick",
        'MagMax2': "Magnitude maximum estimation pick"}
WIDGET_NAMES = ["qToolButton_clearAll", "qToolButton_clearOrigMag", "qToolButton_clearFocMec",
        "qToolButton_doHyp2000", "qToolButton_do3dloc", "qToolButton_doNlloc",
        "qComboBox_nllocModel", "qToolButton_calcMag", "qToolButton_doFocMec",
        "qToolButton_showMap", "qToolButton_showFocMec", "qToolButton_nextFocMec",
        "qToolButton_showWadati", "qToolButton_getNextEvent",
        "qToolButton_updateEventList", "qToolButton_sendEvent", "qToolButton_deleteEvent",
        "qToolButton_deleteEvent", "qCheckBox_sysop", "qLineEdit_sysopPassword",
        "qToolButton_previousStream", "qLabel_streamNumber", "qComboBox_streamName",
        "qToolButton_nextStream", "qToolButton_overview", "qPushButton_phaseType",
        "qComboBox_phaseType", "qToolButton_filter", "qComboBox_filterType",
        "qCheckBox_zerophase", "qLabel_highpass", "qDoubleSpinBox_highpass",
        "qLabel_lowpass", "qDoubleSpinBox_lowpass", "qToolButton_Spectrogram",
        "qCheckBox_spectrogramLog", "qPlainTextEdit_stdout", "qPlainTextEdit_stderr"]
#Estimating the maximum/minimum in a sample-window around click
MAG_PICKWINDOW = 10
MAG_MARKER = {'marker': "x", 'edgewidth': 1.8, 'size': 20}
AXVLINEWIDTH = 1.2
#dictionary for key-bindings
KEYS = {'setPick': 'alt', 'setPickError': ' ', 'delPick': 'escape',
        'setMagMin': 'alt', 'setMagMax': ' ', 'delMagMinMax': 'escape',
        'switchPhase': 'control', 'switchPan': 'p',
        'prevStream': 'y', 'nextStream': 'x', 'switchWheelZoomAxis': 'shift',
        'setWeight': {'0': 0, '1': 1, '2': 2, '3': 3},
        'setPol': {'u': "up", 'd': "down", '+': "poorup", '-': "poordown"},
        'setOnset': {'i': "impulsive", 'e': "emergent"}}
# the following dicts' keys should be all lower case, we use "".lower() later
POLARITY_CHARS = {'up': "U", 'down': "D", 'poorup': "+", 'poordown': "-"}
ONSET_CHARS = {'impulsive': "I", 'emergent': "E",
               'implusive': "I"} # XXX some old events have a typo there... =)


class QMplCanvas(FigureCanvas):
    """
    Class to represent the FigureCanvas widget.
    """
    def __init__(self, parent=None):
        # Standard Matplotlib code to generate the plot
        self.fig = Figure()
        # initialize the canvas where the Figure renders into
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)


def check_keybinding_conflicts(keys):
    """
    check for conflicting keybindings. 
    we have to check twice, because keys for setting picks and magnitudes
    are allowed to interfere...
    """
    for ignored_key_list in [['setMagMin', 'setMagMax', 'delMagMinMax'],
                             ['setPick', 'setPickError', 'delPick']]:
        tmp_keys = copy.deepcopy(keys)
        tmp_keys2 = {}
        for ignored_key in ignored_key_list:
            tmp_keys.pop(ignored_key)
        while tmp_keys:
            key, item = tmp_keys.popitem()
            if isinstance(item, dict):
                while item:
                    k, v = item.popitem()
                    tmp_keys2["_".join([key, str(v)])] = k
            else:
                tmp_keys2[key] = item
        if len(set(tmp_keys2.keys())) != len(set(tmp_keys2.values())):
            err = "Interfering keybindings. Please check variable KEYS"
            raise Exception(err)

def fetch_waveforms_metadata(options):
    """
    Sets up a client and fetches waveforms and metadata according to command
    line options.
    Now also fetches data via arclink (fissures) if --arclink_ids
    (--fissures-ids) is used.
    The arclink (fissures) client is not returned, it is only useful for
    downloading the data and not needed afterwards.
    XXX Notes: XXX
     - there is a problem in the arclink client with duplicate traces in
       fetched streams. therefore at the moment it might be necessary to use
       "-m overwrite" option.

    :returns: (:class:`obspy.seishub.client.Client`,
               list(:class:`obspy.core.stream.Stream`s))
    """
    t = UTCDateTime(options.time)
    t = t + options.starttime_offset
    streams = []
    sta_fetched = set()
    # Seishub
    print "=" * 80
    print "Fetching waveforms and metadata from seishub:"
    print "-" * 80
    baseurl = "http://" + options.servername + ":%i" % options.port
    client = Client(base_url=baseurl, user=options.user,
                    password=options.password, timeout=options.timeout)
    for id in options.ids.split(","):
        net, sta_wildcard, loc, cha = id.split(".")
        for sta in client.waveform.getStationIds(network_id=net):
            if not fnmatch.fnmatch(sta, sta_wildcard):
                continue
            # make sure we dont fetch a single station of
            # one network twice (could happen with wildcards)
            net_sta = "%s.%s" % (net, sta)
            if net_sta in sta_fetched:
                print "%s skipped! (Was already retrieved)" % net_sta
                continue
            try:
                sys.stdout.write("\r%s ..." % net_sta)
                sys.stdout.flush()
                st = client.waveform.getWaveform(net, sta, loc, cha, t,
                        t + options.duration, apply_filter=True,
                        getPAZ=True, getCoordinates=True)
                sta_fetched.add(net_sta)
                sys.stdout.write("\r%s fetched.\n" % net_sta.ljust(8))
                sys.stdout.flush()
            except Exception, e:
                sys.stdout.write("\r%s skipped! (Server replied: %s)\n" % (net_sta, e))
                sys.stdout.flush()
                continue
            for tr in st:
                tr.stats['client'] = "seishub"
            streams.append(st)
    # ArcLink
    if options.arclink_ids:
        from obspy.arclink import Client as AClient
        print "=" * 80
        print "Fetching waveforms and metadata via ArcLink:"
        print "-" * 80
        aclient = AClient(host=options.arclink_servername,
                          port=options.arclink_port,
                          timeout=options.arclink_timeout,
                          user=options.arclink_user,
                          password=options.arclink_password,
                          institution=options.arclink_institution)
        for id in options.arclink_ids.split(","):
            net, sta, loc, cha = id.split(".")
            net_sta = "%s.%s" % (net, sta)
            if net_sta in sta_fetched:
                print "%s skipped! (Was already retrieved)" % net_sta
                continue
            try:
                sys.stdout.write("\r%s ..." % net_sta)
                sys.stdout.flush()
                st = aclient.getWaveform(network_id=net, station_id=sta,
                                         location_id=loc, channel_id=cha,
                                         start_datetime=t,
                                         end_datetime=t + options.duration,
                                         getPAZ=True, getCoordinates=True)
                sta_fetched.add(net_sta)
                sys.stdout.write("\r%s fetched.\n" % net_sta.ljust(8))
                sys.stdout.flush()
            except Exception, e:
                sys.stdout.write("\r%s skipped! (Server replied: %s)\n" % (net_sta, e))
                sys.stdout.flush()
                continue
            for tr in st:
                tr.stats['client'] = "arclink"
            streams.append(st)
    # Fissures
    if options.fissures_ids:
        from obspy.fissures import Client as FClient
        print "=" * 80
        print "Fetching waveforms and metadata via Fissures:"
        print "-" * 80
        fclient = FClient(network_dc=options.fissures_network_dc,
                          seismogram_dc=options.fissures_seismogram_dc,
                          name_service=options.fissures_name_service)
        for id in options.fissures_ids.split(","):
            net, sta, loc, cha = id.split(".")
            net_sta = "%s.%s" % (net, sta)
            if net_sta in sta_fetched:
                print "%s skipped! (Was already retrieved)" % net_sta
                continue
            try:
                sys.stdout.write("\r%s ..." % net_sta)
                sys.stdout.flush()
                st = fclient.getWaveform(network_id=net, station_id=sta,
                                         location_id=loc, channel_id=cha,
                                         start_datetime=t,
                                         end_datetime=t + options.duration,
                                         getPAZ=True, getCoordinates=True)
                sta_fetched.add(net_sta)
                sys.stdout.write("\r%s fetched.\n" % net_sta.ljust(8))
                sys.stdout.flush()
            except Exception, e:
                sys.stdout.write("\r%s skipped! (Server replied: %s)\n" % (net_sta, e))
                sys.stdout.flush()
                continue
            for tr in st:
                tr.stats['client'] = "fissures"
            streams.append(st)
    print "=" * 80
    return (client, streams)

def merge_check_and_cleanup_streams(streams, options):
    """
    Cleanup given list of streams so that they conform with what ObsPyck
    expects.

    Conditions:
    - either one Z or three ZNE traces
    - no two streams for any station (of same network)
    - no streams with traces of different stations

    :returns: (warn_msg, merge_msg, list(:class:`obspy.core.stream.Stream`s))
    """
    # Merge on every stream if this option is passed on command line:
    if options.merge:
        if options.merge.lower() == "safe":
            for st in streams:
                st.merge(method=0)
        elif options.merge.lower() == "overwrite":
            for st in streams:
                st.merge(method=1)
        else:
            err = "Unrecognized option for merging traces. Try " + \
                  "\"safe\" or \"overwrite\"."
            raise Exception(err)

    # Sort streams again, if there was a merge this could be necessary 
    for st in streams:
        st.sort()
        st.reverse()
    sta_list = set()
    # we need to go through streams/dicts backwards in order not to get
    # problems because of the pop() statement
    warn_msg = ""
    merge_msg = ""
    # XXX we need the list() because otherwise the iterator gets garbled if
    # XXX removing streams inside the for loop!!
    for st in list(streams):
        # check for streams with mixed stations/networks and remove them
        if len(st) != len(st.select(network=st[0].stats.network,
                                    station=st[0].stats.station)):
            msg = "Warning: Stream with a mix of stations/networks. " + \
                  "Discarding stream."
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        net_sta = "%s.%s" % (st[0].stats.network.strip(),
                             st[0].stats.station.strip())
        # Here we make sure that a station/network combination is not
        # present with two streams.
        if net_sta in sta_list:
            msg = "Warning: Station/Network combination \"%s\" " + \
                  "already in stream list. Discarding stream." % net_sta
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        if len(st) not in [1, 3]:
            msg = 'Warning: All streams must have either one Z trace ' + \
                  'or a set of three ZNE traces.'
            print msg
            warn_msg += msg + "\n"
            # remove all unknown channels ending with something other than
            # Z/N/E and try again...
            removed_channels = ""
            for tr in st:
                if tr.stats.channel[-1] not in ["Z", "N", "E"]:
                    removed_channels += " " + tr.stats.channel
                    st.remove(tr)
            if len(st.traces) in [1, 3]:
                msg = 'Warning: deleted some unknown channels in ' + \
                      'stream %s.%s' % (net_sta, removed_channels)
                print msg
                warn_msg += msg + "\n"
                continue
            else:
                msg = 'Stream %s discarded.\n' % net_sta + \
                      'Reason: Number of traces != (1 or 3)'
                print msg
                warn_msg += msg + "\n"
                #for j, tr in enumerate(st.traces):
                #    msg = 'Trace no. %i in Stream: %s\n%s' % \
                #            (j + 1, tr.stats.channel, tr.stats)
                msg = str(st)
                print msg
                warn_msg += msg + "\n"
                streams.remove(st)
                merge_msg = '\nIMPORTANT:\nYou can try the command line ' + \
                        'option merge (-m safe or -m overwrite) to ' + \
                        'avoid losing streams due gaps/overlaps.'
                continue
        if len(st) == 1 and st[0].stats.channel[-1] != 'Z':
            msg = 'Warning: All streams must have either one Z trace ' + \
                  'or a set of three ZNE traces.'
            msg += 'Stream %s discarded. Reason: ' % net_sta + \
                   'Exactly one trace present but this is no Z trace'
            print msg
            warn_msg += msg + "\n"
            #for j, tr in enumerate(st.traces):
            #    msg = 'Trace no. %i in Stream: %s\n%s' % \
            #            (j + 1, tr.stats.channel, tr.stats)
            msg = str(st)
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        if len(st) == 3 and (st[0].stats.channel[-1] != 'Z' or
                             st[1].stats.channel[-1] != 'N' or
                             st[2].stats.channel[-1] != 'E'):
            msg = 'Warning: All streams must have either one Z trace ' + \
                  'or a set of three ZNE traces.'
            msg += 'Stream %s discarded. Reason: ' % net_sta + \
                   'Exactly three traces present but they are not ZNE'
            print msg
            warn_msg += msg + "\n"
            #for j, tr in enumerate(st.traces):
            #    msg = 'Trace no. %i in Stream: %s\n%s' % \
            #            (j + 1, tr.stats.channel, tr.stats)
            msg = str(st)
            print msg
            warn_msg += msg + "\n"
            streams.remove(st)
            continue
        sta_list.add(net_sta)
    return (warn_msg, merge_msg, streams)

def setup_dicts(streams):
    """
    Function to set up the list of dictionaries that is used alongside the
    streams list.
    Also removes streams that do not provide the necessary metadata.

    :returns: (list(:class:`obspy.core.stream.Stream`s),
               list(dict))
    """
    #set up a list of dictionaries to store all picking data
    # set all station magnitude use-flags False
    dicts = []
    for i in xrange(len(streams)):
        dicts.append({})
    # we need to go through streams/dicts backwards in order not to get
    # problems because of the pop() statement
    for i in range(len(streams))[::-1]:
        dict = dicts[i]
        st = streams[i]
        trZ = st.select(component="Z")[0]
        if len(st) == 3:
            trN = st.select(component="N")[0]
            trE = st.select(component="E")[0]
        dict['MagUse'] = True
        sta = trZ.stats.station.strip()
        dict['Station'] = sta
        #XXX not used: dictsMap[sta] = dict
        # XXX should not be necessary
        #if net == '':
        #    net = 'BW'
        #    print "Warning: Got no network information, setting to " + \
        #          "default: BW"
        try:
            dict['StaLon'] = trZ.stats.coordinates.longitude
            dict['StaLat'] = trZ.stats.coordinates.latitude
            dict['StaEle'] = trZ.stats.coordinates.elevation / 1000. # all depths in km!
            dict['pazZ'] = trZ.stats.paz
            if len(st) == 3:
                dict['pazN'] = trN.stats.paz
                dict['pazE'] = trE.stats.paz
        except:
            net = trZ.stats.network.strip()
            print 'Error: Missing metadata for %s. Discarding stream.' \
                    % (":".join([net, sta]))
            streams.pop(i)
            dicts.pop(i)
            continue
    return streams, dicts

def setup_external_programs(options):
    """
    Sets up temdir, copies program files, fills in PROGRAMS dict, sets up
    system calls for programs.
    Depends on command line options, returns temporary directory.

    :param options: Command line options of ObsPyck
    :type options: options as returned by :meth:`optparse.OptionParser.parse_args`
    :returns: String representation of temporary directory with program files.
    """
    tmp_dir = tempfile.mkdtemp()
    # set binary names to use depending on architecture and platform...
    env = os.environ
    architecture = platform.architecture()[0]
    system = platform.system()
    global SHELL
    if system == "Windows":
        SHELL = True
    else:
        SHELL = False
    # Setup external programs #############################################
    for prog_basename, prog_dict in PROGRAMS.iteritems():
        prog_srcpath = os.path.join(options.pluginpath, prog_basename)
        prog_tmpdir = os.path.join(tmp_dir, prog_basename)
        prog_dict['dir'] = prog_tmpdir
        shutil.copytree(prog_srcpath, prog_tmpdir, symlinks=True)
        prog_dict['files'] = {}
        for key, filename in prog_dict['filenames'].iteritems():
            prog_dict['files'][key] = os.path.join(prog_tmpdir, filename)
        prog_dict['files']['exe'] = "__".join(\
                [prog_dict['filenames']['exe'], system, architecture])
        # setup clean environment
        prog_dict['env'] = {}
        prog_dict['env']['PATH'] = prog_dict['dir'] + os.pathsep + env['PATH']
        if 'SystemRoot' in env:
            prog_dict['env']['SystemRoot'] = env['SystemRoot']
    # 3dloc ###############################################################
    prog_dict = PROGRAMS['3dloc']
    prog_dict['env']['D3_VELOCITY'] = \
            os.path.join(prog_dict['dir'], 'D3_VELOCITY') + os.sep
    prog_dict['env']['D3_VELOCITY_2'] = \
            os.path.join(prog_dict['dir'], 'D3_VELOCITY_2') + os.sep
    def tmp(prog_dict):
        files = prog_dict['files']
        for file in [files['out'], files['in']]:
            if os.path.isfile(file):
                os.remove(file)
        return
    prog_dict['PreCall'] = tmp
    def tmp(prog_dict):
        sub = subprocess.Popen(prog_dict['files']['exe'], shell=SHELL,
                cwd=prog_dict['dir'], env=prog_dict['env'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        msg = "".join(sub.stdout.readlines())
        err = "".join(sub.stderr.readlines())
        return (msg, err, sub.returncode)
    prog_dict['Call'] = tmp
    # Hyp2000 #############################################################
    prog_dict = PROGRAMS['hyp_2000']
    prog_dict['env']['HYP2000_DATA'] = prog_dict['dir'] + os.sep
    def tmp(prog_dict):
        files = prog_dict['files']
        for file in [files['phases'], files['stations'], files['summary']]:
            if os.path.isfile(file):
                os.remove(file)
        return
    prog_dict['PreCall'] = tmp
    def tmp(prog_dict):
        sub = subprocess.Popen(prog_dict['files']['exe'], shell=SHELL,
                cwd=prog_dict['dir'], env=prog_dict['env'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        input = open(prog_dict['files']['control'], "rt").read()
        (msg, err) = sub.communicate(input)
        return (msg, err, sub.returncode)
    prog_dict['Call'] = tmp
    # NLLoc ###############################################################
    prog_dict = PROGRAMS['nlloc']
    def tmp(prog_dict):
        filepattern = os.path.join(prog_dict['dir'], "nlloc*")
        print filepattern
        for file in glob.glob(filepattern):
            os.remove(file)
        return
    prog_dict['PreCall'] = tmp
    def tmp(prog_dict, controlfilename):
        sub = subprocess.Popen([prog_dict['files']['exe'], controlfilename],
                cwd=prog_dict['dir'], env=prog_dict['env'], shell=SHELL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        msg = "".join(sub.stdout.readlines())
        err = "".join(sub.stderr.readlines())
        for pattern, key in [("nlloc.*.*.*.loc.scat", 'scatter'),
                             ("nlloc.*.*.*.loc.hyp", 'summary')]:
            pattern = os.path.join(prog_dict['dir'], pattern)
            newname = os.path.join(prog_dict['dir'], prog_dict['files'][key])
            for file in glob.glob(pattern):
                os.rename(file, newname)
        return (msg, err, sub.returncode)
    prog_dict['Call'] = tmp
    # focmec ##############################################################
    prog_dict = PROGRAMS['focmec']
    def tmp(prog_dict):
        sub = subprocess.Popen(prog_dict['files']['exe'], shell=SHELL,
                cwd=prog_dict['dir'], env=prog_dict['env'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        msg = "".join(sub.stdout.readlines())
        err = "".join(sub.stderr.readlines())
        return (msg, err, sub.returncode)
    prog_dict['Call'] = tmp
    #######################################################################
    return tmp_dir

#Monkey patch (need to remember the ids of the mpl_connect-statements to remove them later)
#See source: http://matplotlib.sourcearchive.com/documentation/0.98.1/widgets_8py-source.html
class MultiCursor(MplMultiCursor):
    def __init__(self, canvas, axes, useblit=True, **lineprops):
        self.canvas = canvas
        self.axes = axes
        xmin, xmax = axes[-1].get_xlim()
        xmid = 0.5*(xmin+xmax)
        self.lines = [ax.axvline(xmid, visible=False, **lineprops) for ax in axes]
        self.visible = True
        self.useblit = useblit
        self.background = None
        self.needclear = False
        self.id1=self.canvas.mpl_connect('motion_notify_event', self.onmove)
        self.id2=self.canvas.mpl_connect('draw_event', self.clear)
    
   
def gk2lonlat(x, y, m_to_km=True):
    """
    This function converts X/Y Gauss-Krueger coordinates (zone 4, central
    meridian 12 deg) to Longitude/Latitude in WGS84 reference ellipsoid.
    We do this using pyproj (python bindings for proj4) which can be installed
    using 'easy_install pyproj' from pypi.python.org.
    Input can be single coordinates or coordinate lists/arrays.
    
    Useful Links:
    http://pyproj.googlecode.com/svn/trunk/README.html
    http://trac.osgeo.org/proj/
    http://www.epsg-registry.org/
    """
    import pyproj

    proj_wgs84 = pyproj.Proj(init="epsg:4326")
    proj_gk4 = pyproj.Proj(init="epsg:31468")
    # convert to meters first
    if m_to_km:
        x = x * 1000.
        y = y * 1000.
    lon, lat = pyproj.transform(proj_gk4, proj_wgs84, x, y)
    return (lon, lat)

def readNLLocScatter(scat_filename, textviewStdErrImproved):
    """
    This function reads location and values of pdf scatter samples from the
    specified NLLoc *.scat binary file (type "<f4", 4 header values, then 4
    floats per sample: x, y, z, pdf value) and converts X/Y Gauss-Krueger
    coordinates (zone 4, central meridian 12 deg) to Longitude/Latitude in
    WGS84 reference ellipsoid.
    We do this using the Linux command line tool cs2cs.
    Messages on stderr are written to specified GUI textview.
    Returns an array of xy pairs.
    """
    # read data, omit the first 4 values (header information) and reshape
    data = np.fromfile(scat_filename, dtype="<f4").astype("float")[4:]
    data = data.reshape((len(data)/4, 4)).swapaxes(0, 1)
    lon, lat = gk2lonlat(data[0], data[1])
    return np.vstack((lon, lat, data[2]))

def errorEllipsoid2CartesianErrors(azimuth1, dip1, len1, azimuth2, dip2, len2,
                                   len3):
    """
    This method converts the location error of NLLoc given as the 3D error
    ellipsoid (two azimuths, two dips and three axis lengths) to a cartesian
    representation.
    We calculate the cartesian representation of each of the ellipsoids three
    eigenvectors and use the maximum of these vectors components on every axis.
    """
    z = len1 * np.sin(np.radians(dip1))
    xy = len1 * np.cos(np.radians(dip1))
    x = xy * np.sin(np.radians(azimuth1))
    y = xy * np.cos(np.radians(azimuth1))
    v1 = np.array([x, y, z])

    z = len2 * np.sin(np.radians(dip2))
    xy = len2 * np.cos(np.radians(dip2))
    x = xy * np.sin(np.radians(azimuth2))
    y = xy * np.cos(np.radians(azimuth2))
    v2 = np.array([x, y, z])

    v3 = np.cross(v1, v2)
    v3 /= np.sqrt(np.dot(v3, v3))
    v3 *= len3

    v1 = np.abs(v1)
    v2 = np.abs(v2)
    v3 = np.abs(v3)

    error_x = max([v1[0], v2[0], v3[0]])
    error_y = max([v1[1], v2[1], v3[1]])
    error_z = max([v1[2], v2[2], v3[2]])
    
    return (error_x, error_y, error_z)

def formatXTicklabels(x, pos):
    """
    Make a nice formatting for y axis ticklabels: minutes:seconds.microsec
    """
    # x is of type numpy.float64, the string representation of that float
    # strips of all tailing zeros
    # pos returns the position of x on the axis while zooming, None otherwise
    min = int(x / 60.)
    if min > 0:
        sec = x % 60
        return "%i:%06.3f" % (min, sec)
    else:
        return "%.3f" % x