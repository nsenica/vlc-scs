"""
Read REAME.md for instructions

"""

import os
import sys
import json
import datetime
import time
import getch # External py file
import vlc # External py file
import hashlib

# Static global variables
PATH = os.path.abspath(os.path.dirname(__file__))
SCRIPT = os.path.basename(__file__)

# FUTURE IMPROVEMENT
# Add optionParser to allow user to specify config file
config_file = os.path.join(PATH, 'capture.json')
timer_file = os.path.join(PATH, 'schedule.json')
log_file = os.path.join(PATH, "%s.log" % os.path.splitext(SCRIPT)[0])

if sys.platform == "linux" or sys.platform == "linux2":
    # linux
    pass
elif sys.platform == "darwin":
    # OS X
    os.environ['VLC_PLUGIN_PATH'] = '/Applications/VLC.app/Contents/MacOS/'
elif sys.platform == "win32":
    # Windows...
    pass

def writePrint(text):
    '''Write to the log and print to the screen.'''

    f = open(log_file, 'a')
    print text
    f.write(text)
    f.close()


def timePrint(text, dt=None):
    '''Print to STDOUT with a datetime prefix. If no timestamp is provided,
    the current date and time will be used.'''

    if dt is None:
        now = datetime.datetime.now()
        dt = now.strftime('%H:%M:%S')

    writePrint("%s  %s" % (dt, text))


def indentPrint(text):
    '''Print to STDOUT with an indent matching the timestamp printout in
    timePrint().'''

    writePrint("\t    %s" % (text))


def sid(source, channel, programme, start):
    ''' Calculates the sid of a recording '''
    sid = "{0} {1} {2} {3}".format(source, channel, programme, start)
    return hashlib.md5(sid).hexdigest() 

def loadChannelConfig(silent=False):
    '''Load the stream configuration file.'''

    f = open(config_file, 'r')
    cjson = json.load(f)
    f.close()

    channels = len(cjson.keys())
    if not silent:
        writePrint("%d channels available." % channels)

    return cjson


def loadSchedule(silent=False):
    '''Load the scheduled recordings file.'''

    # Read the schedule file
    f = open(timer_file, 'r')
    try:
        rjson = json.load(f)
    except ValueError:
        timePrint('Decoding JSON has failed')
        rjson = json.loads('[]')
        
    f.close()

    recordings = len(rjson)
    if not silent:
        writePrint("%d recordings scheduled." % recordings)

    return rjson


def parseSchedule(schedule, channels):
    '''Parse the schedule and return a list of timings to check against.'''

    recordings = {}
    schedules = len(schedule)

    for x in xrange(0, schedules):
        entry = schedule[x] # should be a JSON object

        # Recording start time
        start = entry['start']
        dt = datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S')

        channel = entry['channel'] # Extract the channel name

        # Check for an endtime or a duration
        endtime = None
        offset = None

        if 'end' in entry:
            endtime = datetime.datetime.strptime(entry['end'], '%Y-%m-%d %H:%M:%S')

        if 'duration' in entry:
            duration = entry['duration'] # Get the timer duration (minutes)
            offset = dt + datetime.timedelta(minutes=duration)

        # Check to see which gives the longer recording - the duration or end timestamp
        if offset is not None and endtime is not None:
            if offset > endtime:
                endtime = offset

        elif offset is not None:
            endtime = offset

        elif endtime is None and offset is None:
            # No valid duration/end time
            writePrint('End or duration missing for scheduled recording %s (%s).' % (dt, channel))
            continue

        elif endtime is not None and endtime < dt:
            # End is earlier than the start!
            writePrint('End timestamp earlier than start! Cannot record %s (%s).' % (dt, channel))

        programme = None

        if 'programme' in entry:
            programme = entry['programme']

        addr = channels[channel] # Get the channel URL
        pid = '%s %s' % (start, channel)

        recordings[pid] = {
            'url': addr,
            'channel': channel,
            'start':dt,
            'end': endtime,
            'programme': programme,
            'sid': sid(addr, channel, programme, dt)
        }

    return recordings


def initialiseTS(channel, tstamp=datetime.datetime.now(), programme=None, ext='.ts'):
    '''Check for a free filename.'''

    # Get list of existing files
    d = set(x for x in os.listdir(PATH) if (x.endswith(ext)))

    # Filename template
    fn = [tstamp.strftime('%Y%m%d_%H%M%S'), channel]

    # If we have a programme name, add it to the filename
    if programme is not None:
        programme.replace(' ', '_') # Replace whitespace with underscores
        fn.append(programme)

    fn_str = '_'.join(fn)
    name = '%s%s' % (fn_str, ext)
    n = 0

    # While a filename matches the standard naming pattern, increment the
    # counter until we find a spare filename
    while name in d:
        name = '%s_%d%s' % (fn_str, n, ext)
        n += 1

    return os.path.join(PATH, name)


def recordStream(instream, outfile):
    '''Record the network stream to the output file.'''

    inst = vlc.Instance() # Create a VLC instance
    p = inst.media_player_new() # Create a player instance
    cmd1 = "sout=file/ts:%s" % outfile
    media = inst.media_new(instream, cmd1)
    media.get_mrl()
    p.set_media(media)
    return (inst, p, media)


def initialise(silent=False):
    '''Load the channel list and scheduled recordings.'''

    # Initial startup
    channels = loadChannelConfig(silent) # Get the available channels
    schedule = loadSchedule(silent) # Get the schedule
    recordings = parseSchedule(schedule, channels) # Parse the schedule information

    return recordings


def reloadSchedule(existing, running):
    '''Reload the list of scheduled recordings.'''

    now = datetime.datetime.now() # Get the current timestamp
    revised = initialise(True) # Get the revised schedule

    # Get the schedule id for each of the running recordings
    running_ids = {}
    for r in running:
        sid = running[r]['sid']
        running_ids[sid] = r

    new = {}

    # Number of new entries
    new_rec = 0
    old_rec = len(existing)

    # Compare the revised schedule against the existing
    for r in revised:
        data = revised[r]
        sched_id = data['sid']
        endtime = data['end']

        # If this recording is already running
        if sched_id in running_ids.keys():
            h = running_ids[sched_id]

            # If it's the same schedule (source, channel, programme), check if we need to revise the end time
            if endtime != running[h]['end']:
                timePrint('Changed end time for running recording:')

                if data['programme'] is not None:
                    indentPrint('%(programme)s (%(channel)s)' % data)
                else:
                    indentPrint('%s' % h)

                indentPrint('%s to %s' % (running[h]['end'].strftime('%Y-%m-%d %H:%M:%S'), endtime.strftime('%Y-%m-%d %H:%M:%S')))

                running[h]['end'] = endtime

        # Otherwise, it's not a currently-running recording
        # We only want to consider programmes that haven't finished yet
        elif endtime > now:
            new_rec += 1
            new[r] = data

    

    if old_rec > 0:
        timePrint('Removed %d new scheduled recordings.' % old_rec)

    if new_rec > 0:
        timePrint('Added %d new scheduled recordings.' % new_rec)

    return (new, running)

def printSchedule(recordings, handles):

    hs = handles.keys()
    if hs:
        print 'Recording: '
    for h in sorted(hs):
        printHandle(handles[h])

    rs = recordings.keys()
    if rs:
        print 'Schedule: '
    for r in sorted(rs):
        printRecord(recordings[r])

def printHandle(handle):
    end = handle['end']
    channel = handle['channel']
    programme = handle['programme']
    print 'End: %s Channel: %s Programme: %s ' % (end, channel, programme)

def printRecord(record):
    start = record['start']
    end = record['end']
    channel = record['channel']
    programme = record['programme']
    print 'From: %s To: %s Channel: %s Programme: %s ' % (start, end, channel, programme)

def main():
    recordings = initialise() # Load the channels and schedule
    handles = {} # Create storage for the recording handles
    busy = True

    lastUpdatedAt = datetime.datetime.now()

    while busy:
        now = datetime.datetime.now() # Get the current timestamp
        sinceLastUpdate = now - lastUpdatedAt
        
        if ( sinceLastUpdate.total_seconds() > 3600 ):
            timePrint("Auto reloading schedule")
            (recordings, handles) = reloadSchedule(recordings, handles)
            lastUpdatedAt = now

        # Check existing recordings
        hs = handles.keys()
        for h in hs:
            data = handles[h]
            end = data['end']
            channel = data['channel']
            programme = data['programme']

            if now > end:
                timePrint("Finished recording %s (%s)." % (programme, channel))
                try:
                    data['player'].stop() # Stop playback
                    data['player'].release() # Close the player
                    data['inst'].release() # Destroy the instance
                except Exception, err:
                    timePrint("Unable to destroy player reference due to error:")
                    writePrint(str(err))
                handles.pop(h) # Remove the handle to the player

        # Loop through the schedule
        rs = recordings.keys()
        for r in rs:
            data = recordings[r] # Schedule entry details
            start = data['start']
            end = data['end']
            channel = data['channel']
            programme = data['programme']

            # If we're not recording the stream but we're between the
            # start and end times for the programme, record it
            if r not in handles and (now > start):
                if (now < end):
                    # Determine a suitable output filename
                    fn = initialiseTS(channel, start, programme)

                    # Create the VLC instance and player
                    (inst, player, media) = recordStream(data['url'], fn)

                    # Store the handle to the VLC instance and relevant data
                    handles[r] = {
                        'inst': inst,
                        'player': player,
                        'media': media,
                        'end': end,
                        'programme': programme,
                        'channel': channel,
                        'sid': data['sid']
                    }

                    # Start the stream and hence the recording
                    player.play()
                    timePrint("Started recording:")
                    indentPrint("%s (%s)" % (programme, channel))
                    indentPrint("%s to %s" % (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')))

                else:
                    timePrint("Missed scheduled recording:")
                    indentPrint("%s (%s)" % (programme, channel))
                    indentPrint("%s to %s" % (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')))

                # Remove the item from the schedule to prevent it being
                # processed again
                recordings.pop(r)

        k = len(handles.keys()) + len(recordings.keys())
        #busy = k > 0

        # Loop for 10 seconds, checking for a keyhit
        n = 10
        while n > 0:
            keyhit = getch.getch()
            n -= 1

            # Check if we have a keyhit
            if keyhit is not None:
                kl = keyhit.lower()

                # Reload schedule
                if 'r' in kl:
                    timePrint('Reloading schedule...')
                    (recordings, handles) = reloadSchedule(recordings, handles)

                # Reload channel config
                if 'c' in kl:
                    pass

                if 'i' in kl:
                    timePrint('Reinitialise channels and schedule...')
                    recordings = initialise(True)

                # List scheduled recordings
                if 'l' in kl:
                    printSchedule(recordings, handles)

                # Quit
                if 'q' in kl:
                    # Force quit if q is pressed twice
                    if not busy:
                        exit()
                    # Add request for confirmation here
                    busy = False

        if not busy:
            timePrint("Exiting...\n")


if __name__ == '__main__':
    main()
