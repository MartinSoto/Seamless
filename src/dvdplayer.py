# Seamless DVD Player
# Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA

import time

import gobject

import gst
import gst.interfaces

# FIXME: get rid of this
from gst import *

# Load private GStreamer plugins.
import loadplugins

from machine import *


#
# Main DVD Player Class
#

def ghostify(bin, elemName, padName, ghostName=None):
    if not ghostName:
        ghostName = padName
    bin.add_ghost_pad(bin.get_by_name(elemName).get_pad(padName), ghostName)


class DVDPlayer(Thread):
    """
    """

    def __init__(self, name="player", location="/dev/dvd"):
        Thread.__init__(self, name)

        # Create an info object for the DVD.
        self.info = DVDInfo(location)

        # Build the pipeline.

        #timeout = "timeout=10000000"
        timeout = ""
        self.dvdSrc = parse_launch("""
        (
          dvdblocksrc name=dvdblocksrc !
            seamless-dvddemux name=dvddemux .current_video !
            mpeg2dec name=mpeg2dec !
            queue name=video %s
          dvddemux.current_subpicture !
            queue name=subtitle %s
          dvddemux.current_audio !
            queue name=audio max-size-buffers=50
        )
        """ % (timeout, timeout))
        ghostify(self.dvdSrc, 'video', 'src', 'video')
        ghostify(self.dvdSrc, 'subtitle', 'src', 'subtitle')
        ghostify(self.dvdSrc, 'audio', 'src', 'audio')
        self.add(self.dvdSrc)

        #self.videoSink = sinkFromSpec("""
        #  { queue name=queue max-size-buffers=150 !
        #    fakesink }""")
        #self.videoSink = sinkFromSpec("""
        #  { queue name=queue max-size-buffers=150 !
        #    dxr3videosink }
        #    """)
        #self.videoSink = sinkFromSpec("""
        #{
        #  queue name=queue max-size-buffers=150 ! filesink location=video.out
        #}
        #""")
        #self.add(self.videoSink)
        #self.videoSink = sinkFromSpec("""
        #  { queue name=queue max-size-buffers=150 !
        #    fdsink fd=1 }
        #    """)
        self.videoSink = parse_launch("""
        {
          seamless-mpeg2subt name=mpeg2subt !
            identity name=videoident !
            xvimagesink name=videosink brightness=40 hue=1000
        }
        """)
        # For 16:9:  pixel-aspect-ratio=4/3
#         self.videoSink = parse_launch("""
#         {
#           mpeg2subt name=mpeg2subt !
#             identity name=videoident !
#             ffcolorspace !
#             videoscale !
#             ximagesink name=videosink
#         }
#         """)
        ghostify(self.videoSink, 'mpeg2subt', 'video')
        ghostify(self.videoSink, 'mpeg2subt', 'subtitle')
        self.videoSinkElem = self.videoSink.get_by_name('videosink')
        self.videoIdent = self.videoSink.get_by_name('videoident')
        self.add(self.videoSink)

        #self.audioSink = sinkFromSpec("""
        #  { queue name=queue !
        #    fakesink }
        #    """)
        #self.audioSink = sinkFromSpec("""
        #  { queue name=queue ! a52dec ! osssink }
        #    """)
        #self.audioSink = sinkFromSpec("""
        #  { queue name=queue ! filesink location=audio.out }
        #  """)
        self.audioSink = parse_launch("""
        {
          ac3iec958 name=ac3iec958 !
            identity name=audioident !
            alsaspdifsink name=audiosink
        }
        """)
        ghostify(self.audioSink, 'ac3iec958', 'sink', 'audio')
#         self.audioSink = parse_launch("""
#         {
#           a52dec name=a52dec !
#             identity name=audioident !
#             alsasink name=audiosink
#         }
#         """)
#         ghostify(self.audioSink, 'a52dec', 'sink', 'audio')
        self.audioSinkElem = self.audioSink.get_by_name('audiosink')
        self.audioIdent = self.audioSink.get_by_name('audioident')
        self.add(self.audioSink)

        self.dvdSrc.link_pads('video', self.videoSink, 'video')
        self.dvdSrc.link_pads('subtitle', self.videoSink, 'subtitle')
        self.dvdSrc.link_pads('audio', self.audioSink, 'audio')

        # Distribute the clock manually.
        clock = self.audioSinkElem.get_clock()
        self.videoSink.use_clock(clock)
        self.audioSink.use_clock(clock)

        # Wrap the source element in the virtual machine.
        self.machine = VirtualMachine(self.info,
                                      self.dvdSrc.get_by_name('dvdblocksrc'))

        #self.videoIdent.connect('handoff', self.identHandoff)
        #self.audioIdent.connect('handoff', self.identHandoff)


    def identHandoff(self, elem, *args):
        print "Handoff: %s" % elem.get_name()
        #pass

    def getVideoSink(self):
        return self.videoSinkElem


    #
    # Player Control
    #

    def __getattr__(self, name):
        # Make this object a proxy for the virtual machine.
        return getattr(self.machine, name)

    def start(self):
        self.set_state(STATE_PLAYING)

    def stop(self):
        self.machine.stop()

        # Wait for the pipeline to actually stop. If waiting time is
        # too long, just give up and hope for the best.
        maxIter = 40
        while maxIter > 0 and self.get_state() == gst.STATE_PLAYING:
            time.sleep(0.1)
            maxIter -= 1

        self.set_state(STATE_NULL)

    def backward10(self):
        self.machine.timeJumpRelative(-10)

    def forward10(self):
        self.machine.timeJumpRelative(10)


    def nextAudioStream(self):
        streamNumbers = map(lambda x: x[0],
                            self.machine.getAudioStreams())
        if len(streamNumbers) == 0:
            return

        try:
            pos = streamNumbers.index(self.machine.audioStream)
        except:
            return

        self.machine.audioStream = streamNumbers[(pos + 1) % \
                                                 len(streamNumbers)]
