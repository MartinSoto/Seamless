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

# Load private GStreamer plugins.
import loadplugins

import dvdread
import machine
import wrapclock


#
# Main DVD Player Class
#

def ghostify(bin, elemName, padName, ghostName=None):
    if not ghostName:
        ghostName = padName
    bin.add_ghost_pad(bin.get_by_name(elemName).get_pad(padName), ghostName)


class DVDPlayer(gst.Thread):
    """
    """

    def __init__(self, options, name="player"):
        gst.Thread.__init__(self, name)

        # Create an info object for the DVD.
        self.info = dvdread.DVDInfo(options.location)

        # Build the pipeline.

        # The backend thread.
        if options.videoDecode == 'soft':
            videoDecoder = 'mpeg2dec name=mpeg2dec !'
        else:
            videoDecoder = ''

        self.dvdSrc = gst.parse_launch("""
        (
          dvdblocksrc name=dvdblocksrc location=%s !
            seamless-dvddemux name=dvddemux .current_video !
            %s
            seamless-queue name=video
          dvddemux.current_subpicture !
            seamless-queue name=subtitle
          dvddemux.current_audio !
            seamless-queue name=audio max-size-buffers=50
        )
        """ % (options.location, videoDecoder))
        ghostify(self.dvdSrc, 'video', 'src', 'video')
        ghostify(self.dvdSrc, 'subtitle', 'src', 'subtitle')
        ghostify(self.dvdSrc, 'audio', 'src', 'audio')
        self.add(self.dvdSrc)

        # The video playback thread.
        self.videoSink = gst.parse_launch("""
        {
          seamless-mpeg2subt name=mpeg2subt !
            identity name=videoident !
            %s name=videosink
        }
        """ % options.videoSink)
        ghostify(self.videoSink, 'mpeg2subt', 'video')
        ghostify(self.videoSink, 'mpeg2subt', 'subtitle')
        self.videoSinkElem = self.videoSink.get_by_name('videosink')
        self.videoIdent = self.videoSink.get_by_name('videoident')
        self.add(self.videoSink)

        # The audio playback thread.
        if options.audioDecode == 'soft':
            sinkName = 'a52dec'
            audioDecoder = 'a52dec name=%s ! audioconvert ! audioscale !' \
                           % sinkName
        else:
            sinkName = 'audioident'
            audioDecoder = ''

        self.audioSink = gst.parse_launch("""
        {
          %s
            identity name=audioident !
            %s name=audiosink
        }
        """ % (audioDecoder, options.audioSink))
        ghostify(self.audioSink, sinkName, 'sink', 'audio')
        self.audioSinkElem = self.audioSink.get_by_name('audiosink')
        self.audioIdent = self.audioSink.get_by_name('audioident')
        self.add(self.audioSink)

        # All together now.
        self.dvdSrc.link_pads('video', self.videoSink, 'video')
        self.dvdSrc.link_pads('subtitle', self.videoSink, 'subtitle')
        self.dvdSrc.link_pads('audio', self.audioSink, 'audio')

        if options.clockType == 'robust':
            # Wrap the clock in a robust clock.
            self.clock = wrapclock.wrap(self.audioSinkElem.get_clock())
        elif options.clockType == 'audiosink':
            self.clock = self.audioSinkElem.get_clock()
        elif options.clockType == 'system':
            self.clock = gst.system_clock_obtain()
        else:
            assert 0, 'Unexpected clock type'
        self.use_clock(self.clock)
        

        # Wrap the source element in the virtual machine.
        self.shell = machine.MachineShell(self.info,
                                          self.dvdSrc. \
                                          get_by_name('dvdblocksrc'))

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
        return getattr(self.shell, name)

    def start(self):
        self.set_state(gst.STATE_PLAYING)

    def stop(self):
        self.shell.stop()

        # Wait for the pipeline to actually stop. If waiting time is
        # too long, just give up and hope for the best.
        maxIter = 40
        while maxIter > 0 and self.get_state() == gst.STATE_PLAYING:
            time.sleep(0.1)
            maxIter -= 1

        self.set_state(gst.STATE_NULL)

    def backward10(self):
        if self.shell.canPositionSeek():
            self.shell.seekToPositionRelative(-10)

    def forward10(self):
        if self.shell.canPositionSeek():
            self.shell.seekToPositionRelative(10)


    def nextAudioStream(self):
        streamNumbers = map(lambda x: x[0],
                            self.shell.getAudioStreams())
        if len(streamNumbers) == 0:
            return

        try:
            pos = streamNumbers.index(self.shell.audioStream)
        except:
            return

        self.shell.audioStream = streamNumbers[(pos + 1) % \
                                               len(streamNumbers)]
