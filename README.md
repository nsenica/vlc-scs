VLC Stream Saver Scheduler
======================

Script authored by jwhite88 and downloaded from [http://code.activestate.com/recipes/579096-vlcpy-stream-capture-scheduler-script/](http://code.activestate.com/recipes/579096-vlcpy-stream-capture-scheduler-script/)

A script to capture network streams using VLC, based on a scheduler. It was originally designed for mpeg transport streams on the local network, but can be modified for other stream types. It runs as an infinite loop and can be terminated by pressing "Q" (see below for key commands).

Last updated 19th August 2015.


Dependencies:

* My fork of Danny Yoo's getch()-like function: [https://code.activestate.com/recipes/579095](https://code.activestate.com/recipes/)
* vlc.py http://wiki.videolan.org/Python_bindings


The end user will need to create two JSON files in the same directory as the script:

* capture.json to store the network stream/channel information
* schedule.json to store the timer recordings


Example format of capture.json:

```json
    {
    "stream name one":"stream one address",
    "stream name two":"stream two address"
    }
```

Example format of schedule.json:

```json
[
    { "start":"2015-08-18 18:08:00", "duration":1, "channel":"stream name one", "programme":"Test Recording"},
    { "start":"2015-08-18 19:20:00", "end":"2015-08-18 20:20:00", "channel":"stream name two", "programme":"Second Recording"}
]
```

You can specify either the length of the recording or an end datetime. The programme field is simply a descriptor (the recording will be named YYYYMMDD_HHMMSS_channel_programme.ts).


Commands:

Once the script is running, it will automatically parse the channel list and schedule. There are three basic commands, trigger by key presses:

* pressing "R" reloads the schedule and will update any upcoming scheduled recordings
* pressing "C" reloads the channel list
* pressing "Q" exits the script