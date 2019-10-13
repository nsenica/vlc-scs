'''
This expects a file named shows.json with the following format:

{
    "CaptureStream" : {       <-- As in capture.json
        "Title" : {           <-- Looks for this string in the show title
            "1" : [           <-- Seasons to look for [1]
                "26-35"       <-- Episodes to look for [1]
                ],
            ...
        }
    }
}

Reads an EPG xmltv file named guide.xml with `episode-num` tag to match them
with the definition above.

Outputs to the STDOUT the resulting schedule to record the
matching titles in the right format to feed vlc-scs.py.

[1] Season and episodes can have several formats: 
    - Individual (i.e. 1, 2, 3)
    - Range (i.e. 1-5 inclusive)
    - Range with no end (i.e. 5+ inclusive)

'''

import xmltv
import re
from pprint import pprint
from datetime import datetime, timedelta
import json
import pytz


timezone = pytz.timezone("Europe/Amsterdam")
tvseries = json.load(open("shows.json"))
filename = "guide.xml"

xmltv.read_data(open(filename, 'r'))
programmes = xmltv.read_programmes(open(filename, 'r'))

result = list()

def _should_get(num, numSet):

    if not numSet:
        return 1

    for val in numSet:

        if val.find("-") != -1:
            sval = int(val.split("-")[0])
            fval = int(val.split("-")[1])

            if (num >= sval and num <= fval):
                return 1
        elif val[-1] == "+":
            sval = int(val.split("+")[0])
            if num >= sval:
                return 1
        elif int(val) == num:
            return 1
    return 0

def add_schedule(programme):

    start = datetime.strptime(programme["start"], "%Y%m%d%H%M%S %z")
    start -= timedelta( minutes = 5)
    start = start.astimezone(timezone)
    stop = datetime.strptime(programme["stop"], "%Y%m%d%H%M%S %z")
    stop += timedelta( minutes = 10)
    stop = stop.astimezone(timezone)

    if stop.astimezone(pytz.utc) < datetime.now(pytz.utc):
        return

    title = programme["title"][0][0]
    title = title.translate({ord(ch):'_' for ch in ' ,:'})
    title = title.translate({ord(ch):'' for ch in '.'})
    title = title.translate({ord(ch):'i' for ch in 'í'})
    title = title.translate({ord(ch):'a' for ch in 'ã'})

    rec = {
        "start" : start.strftime("%Y-%m-%d %H:%M:%S"),
        "end" : stop.strftime("%Y-%m-%d %H:%M:%S"),
        "channel" : programme["channel"],
        "programme" : title
    }

    if len(result) == 0:
        result.append(rec)
        return

    should_add = 1
    for r in result:
        if r["channel"] != rec["channel"]:
            continue

        # Similar entry exists.. bailing out.
        if r["channel"] == rec["channel"] and r["start"] == rec["start"] and r["end"] == rec["end"] and r["programme"] == rec["programme"]:
            should_add = 0
            break 

        # Full show is already contained in a recording, append the title
        # but don't do anything else
        if rec["start"] >= r["start"] and rec["end"] <= r["end"]:
            r["programme"] = r["programme"] + "_" + rec["programme"]
            should_add = 0
            break
        
        # New recording starts before but overlaps at the beginning.
        # Extend current recording.
        if rec["start"] < r["start"] and rec["end"] >= r["start"] and rec["end"] <= r["end"]:
            r["programme"] = rec["programme"] + "_" + r["programme"]
            r["start"] = rec["start"]
            should_add = 0
            break

        # New recording ends after but overlaps at the end.
        # Extend current recording.
        if rec["start"] > r["start"] and rec["start"] < r["end"] and rec["end"] > r["end"]:
            r["programme"] = r["programme"] + "_" + rec["programme"]
            r["end"] = rec["end"]
            should_add = 0
            break

        # New recording starts before and ends after the current one.
        # Extend current recording.
        if rec["start"] < r["start"] and rec["end"] > r["end"]:
            r["programme"] = r["programme"] + "_" + rec["programme"]
            r["start"] = rec["start"]
            r["end"] = rec["end"]
            should_add = 0
            break

    if should_add:
        # It's a new disjoint recording, adding it to the end result
        result.append(rec)


for p in programmes:
    current = tvseries.get(p["channel"])
    if not current:
        continue

    for key in current.keys():
        show = current[key]
        title = p["title"][0][0]
        if title.lower().find(key.lower()) == -1:
            continue

        if not p.get("episode-num"):
            continue

        ns = p["episode-num"][0][0]
        ns_array = ns.split('.')
        ns_season = ns_array[0] or 0
        ns_season = int(ns_season)+1
        ns_episode = ns_array[1]
        ns_episode = int(ns_episode)+1

        for season in show.keys():

            if not _should_get(ns_season, [ season ]  ):
                continue

            show_epi = show.get(season)

            if show_epi == None:
                continue

            if _should_get(ns_episode, show_epi):
                add_schedule(p)

result = sorted(result, key=lambda k: k['start'])

print(json.dumps(result, indent=4))

with open("schedule.json", "w") as write_file:
    json.dump(result,write_file, indent=4)