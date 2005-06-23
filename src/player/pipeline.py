# Seamless DVD Player
# Copyright (C) 2004-2005 Martin Soto <martinsoto@users.sourceforge.net>
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


class ParsedBin(gst.Bin):
    """A GStgreamer bin whose contents are created by parsing a pipeline
    specification."""

    __slots__ = ()

    def __init__(self, name, pipelineSpec):
        gst.Bin.__init__(self, name)

        elem = gst.parse_launch(pipelineSpec)
        if isinstance(elem, gst.Bin):
            # Move all elements to this instance. Yes, this is sort of
            # funny, but the GStreamer API doesn't offer anything
            # better at the moment.
            for subelem in elem.get_list():
                elem.remove(subelem)
                self.add(subelem)
        else:
            self.add(elem)

    def ghostify(self, elemName, padName, ghostName=None):
        if not ghostName:
            ghostName = padName
        self.add_ghost_pad(self.get_by_name(elemName).get_pad(padName),
                           ghostName)


class SoftwareAudio(ParsedBin):
    """An audio playback element that uses software decoders for AC3
    and DTS."""

    __slots__ = ('clock')

    def __init__(self, options, name='audiodec'):
        super(SoftwareAudio, self).__init__(name, """
        (
          capsselect name=capsselect !
            seamless-a52dec !
            audioconvert !
            audioscale !
            capsaggreg name=capsaggreg !
            seamless-queue name=audioqueue !
            { %(audioSink)s name=audiosink }

          capsselect.src%%d !
            dvdlpcmdec !
            audioconvert !
            audioscale ! capsaggreg.sink%%d

          capsselect.src%%d !
            dtsdec !
            audioconvert !
            audioscale ! capsaggreg.sink%%d
        )
        """ % options)
        self.ghostify('capsselect', 'sink')

        self.clock = self.get_by_name('audiosink').get_clock()

    def getClock(self):
        return self.clock


class SpdifAudio(ParsedBin):
    """An audio playback element that feeds AC3 sound (DTS coming
    soon) to an external hardware decoder through an SP/DIF digital
    audio interface. The SP/DIF device is driven using ALSA."""

    __slots__ = ('clock')

    def __init__(self, options, name='audiodec'):
        super(SpdifAudio, self).__init__(name, """
        (
          capsselect name=capsselect !
            ac3iec958 !
            capsaggreg name=capsaggreg !
            seamless-queue max-size-bytes=40000 !
            { alsasink name=audiosink }

          capsselect.src%d !
            dvdlpcmdec !
            audioconvert !
            audioscale ! capsaggreg.sink%d

          capsselect.src%d !
            dtsdec !
            audioconvert !
            audioscale ! capsaggreg.sink%d
        )
        """)
        audioElem = self.get_by_name('audiosink')

        # Can gstparse set property values with spaces?
        audioElem.set_property('device',
            'spdif:{AES0 0x0 AES1 0x82 AES2 0x0 AES3 0x2 CARD %(spdifCard)s}' %
            options)
        
        self.ghostify('capsselect', 'sink')

        self.clock = audioElem.get_clock()

    def getClock(self):
        return self.clock


class SoftwareVideo(ParsedBin):
    """A video playback element that decodes MPEG2 video using a
    software decoder."""

    __slots__ = ()

    def __init__(self, options, name='videodec'):
        super(SoftwareVideo, self).__init__(name, """
        (
          mpeg2dec name=mpeg2dec !
            {
              seamless-queue !
                .video seamless-mpeg2subt name=mpeg2subt !
                ffmpegcolorspace !
                videoscale !
                seamless-queue max-size-buffers=3 name=videoqueue !
                { %(videoSink)s name=videosink }

              seamless-queue name=subtitle ! mpeg2subt.subtitle
            }
        )
        """ % options)

        self.ghostify('mpeg2dec', 'sink', 'video')
        self.ghostify('subtitle', 'sink', 'subtitle')


class BackPlayer(ParsedBin):
    """The backend playback element that reads material from the DVD
    disk, demultiplexes it, and feeds to the front-end playback
    elemens."""

    __slots__ = ()

    def __init__(self, options, name='backplayer'):
        super(BackPlayer, self).__init__(name, """
        (
          dvdblocksrc name=dvdblocksrc location=%(location)s !
            seamless-dvddemux name=dvddemux
        )
        """ % options)

        self.ghostify('dvddemux', 'current_video', 'video')
        self.ghostify('dvddemux', 'current_subpicture', 'subtitle')
        self.ghostify('dvddemux', 'current_audio', 'audio')

    def getBlockSource(self):
        return self.get_by_name('dvdblocksrc')


class Pipeline(gst.Thread):
    """The GStreamer pipeline used to play DVDs."""

    __slots__ = ('backPlayer',
                 'audioSink', 
                 'videoSink',
                 'clock')

    def __init__(self, options, name="dvdplayer"):
        gst.Thread.__init__(self, name)

        # Build the pipeline.

        # The back player.
        self.backPlayer = BackPlayer(options)
        self.add(self.backPlayer)

        # The video playback element.
        self.videoSink = SoftwareVideo(options)
        self.add(self.videoSink)

        # The audio playback element.
        if options.spdifCard:
            self.audioSink = SpdifAudio(options)
        else:
            self.audioSink = SoftwareAudio(options)
        self.add(self.audioSink)

        # All together now.
        self.backPlayer.link_pads('video', self.videoSink, 'video')
        self.backPlayer.link_pads('subtitle', self.videoSink, 'subtitle')
        self.backPlayer.link_pads('audio', self.audioSink, 'sink')

        # Set an appropriate clock for the pipeline.
        if options.clockType == 'robust':
            # Wrap the clock in a robust clock.
            self.clock = wrapclock.wrap(self.audioSink.getClock())
        elif options.clockType == 'audiosink':
            self.clock = self.audioSink.getClock()
        elif options.clockType == 'system':
            self.clock = gst.system_clock_obtain()
        else:
            assert 0, 'Unexpected clock type'
        self.use_clock(self.clock)


    #
    # Component Retrieval
    #

    def getBlockSource(self):
        return self.backPlayer.getBlockSource()

    def getVideoSink(self):
        return self.videoSink.get_by_name('videosink')


    #
    # Playback Control
    #

    def start(self):
        self.set_state(gst.STATE_PLAYING)

    def forceStop(self):
        self.set_state(gst.STATE_NULL)

    def waitForStop(self):
        """Wait for the pipeline to actually stop. If waiting time is
        too long, just force a stop."""
        maxIter = 40
        while maxIter > 0 and self.get_state() == gst.STATE_PLAYING:
            time.sleep(0.1)
            maxIter -= 1

        self.forceStop()

