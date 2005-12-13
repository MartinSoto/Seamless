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
# import wrapclock


class MySink(gst.Element):

    _sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
                                        gst.PAD_SINK,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    def __init__(self):
        gst.Element.__init__(self)
        gst.info('creating sinkpad')
        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        gst.info('adding sinkpad to self')
        self.add_pad(self.sinkpad)

        gst.info('setting chain/event functions')
        self.sinkpad.set_chain_function(self.chainfunc)
        self.sinkpad.set_event_function(self.eventfunc)
        
    def chainfunc(self, pad, buffer):
        if buffer.timestamp != gst.CLOCK_TIME_NONE:
            self.info("%s timestamp: %0.3fs" % (pad,
                                                float(buffer.timestamp) /
                                                gst.SECOND))
        return gst.FLOW_OK

    def eventfunc(self, pad, event):
        if event.type == gst.EVENT_NEWSEGMENT:
            (update, rate, format, start, stop, position) = \
                     event.parse_new_segment()
            self.info("%s event: %r: start=%0.3fs, stop=%0.3fs" % \
                      (pad, event.type, float(start) / gst.SECOND,
                       float(stop) / gst.SECOND))
        else:
            self.info("%s event: %r" % (pad, event.type))
        return True

gobject.type_register(MySink)


class Bin(gst.Bin):
    """An enhanced GStgreamer bin."""

    __slots__ = ()

    def makeSubelem(self, type, name=None, **keywords):
        if name == None:
            name = type

        subelem = gst.element_factory_make(type, name)

        for (prop, value) in keywords.items():
            subelem.set_property(prop, value)

        self.add(subelem)

        return subelem

    def ghostify(self, elemName, padName, ghostName=None):
        if not ghostName:
            ghostName = padName
        self.add_pad(gst.GhostPad(ghostName,
                                  self.get_by_name(elemName).get_pad(padName)))

    def link(self, elemName1, elemName2):
        elem1 = self.get_by_name(elemName1)
        elem2 = self.get_by_name(elemName2)

        elem1.link(elem2)
        
    def linkPads(self, elemName1, padName1, elemName2, padName2):
        elem1 = self.get_by_name(elemName1)
        elem2 = self.get_by_name(elemName2)

        elem1.link_pads(padName1, elem2, padName2)


class SoftwareAudio(Bin):
    """An audio playback element that uses software decoders for AC3
    and DTS."""

    __slots__ = ('clock')

    def __init__(self, options, name='audiodec'):
#         super(SoftwareAudio, self).__init__(name, """
#         (
#           capsselect name=capsselect !
#             seamless-a52dec !
#             audioconvert !
#             audioscale !
#             capsaggreg name=capsaggreg !
#             seamless-queue name=audioqueue !
#             { %(audioSink)s name=audiosink }

#           capsselect.src%%d !
#             dvdlpcmdec !
#             audioconvert !
#             audioscale ! capsaggreg.sink%%d

#           capsselect.src%%d !
#             dtsdec !
#             audioconvert !
#             audioscale ! capsaggreg.sink%%d
#         )
#         """ % options)
        super(SoftwareAudio, self).__init__(name)

        self.makeSubelem('a52dec')
        self.makeSubelem('audioconvert')
        self.makeSubelem('queue')
        self.makeSubelem(options['audioSink'], 'audiosink')
        
        self.link('a52dec', 'audioconvert')
        self.link('audioconvert', 'queue')
        self.link('queue', 'audiosink')

        self.ghostify('a52dec', 'sink')


class SpdifAudio(Bin):
    """An audio playback element that feeds AC3 sound (DTS coming
    soon) to an external hardware decoder through an SP/DIF digital
    audio interface. The SP/DIF device is driven using ALSA."""

    __slots__ = ('clock')

    def __init__(self, options, name='audiodec'):
#         super(SpdifAudio, self).__init__(name, """
#         (
#           capsselect name=capsselect !
#             ac3iec958 !
#             capsaggreg name=capsaggreg !
#             seamless-queue max-size-bytes=40000 !
#             { alsasink name=audiosink }

#           capsselect.src%d !
#             dvdlpcmdec !
#             audioconvert !
#             audioscale ! capsaggreg.sink%d

#           capsselect.src%d !
#             dtsdec !
#             audioconvert !
#             audioscale ! capsaggreg.sink%d
#         )
#         """)
        super(SpdifAudio, self).__init__(name, """( fakesink name=capselect )""")
        audioElem = self.get_by_name('audiosink')

#         # Can gstparse set property values with spaces?
#         audioElem.set_property('device',
#             'spdif:{AES0 0x0 AES1 0x82 AES2 0x0 AES3 0x2 CARD %(spdifCard)s}' %
#             options)
        
        self.ghostify('capsselect', 'sink')


class SoftwareVideo(Bin):
    """A video playback element that decodes MPEG2 video using a
    software decoder."""

    __slots__ = ()

    def __init__(self, options, name='videodec'):
#         super(SoftwareVideo, self).__init__(name, """
#         (
#           mpeg2dec name=mpeg2dec !
#             {
#               seamless-queue !
#                 .video seamless-mpeg2subt name=mpeg2subt !
#                 ffmpegcolorspace !
#                 videoscale !
#                 seamless-queue max-size-buffers=3 name=videoqueue !
#                 { %(videoSink)s name=videosink }

#               seamless-queue name=subtitle ! mpeg2subt.subtitle
#             }
#         )
#         """ % options)
        super(SoftwareVideo, self).__init__(name)

        self.makeSubelem('mpeg2dec')
        self.makeSubelem('queue', 'video-queue',
                         max_size_bytes=1024 * 1024 * 32)
        self.makeSubelem('mpeg2subt')
        self.makeSubelem('ffmpegcolorspace')
        self.makeSubelem('videoscale')
        self.makeSubelem(options['videoSink'], 'videosink',
                         force_aspect_ratio=True,
                         pixel_aspect_ratio=options['pixelAspect'])

        self.link('mpeg2dec', 'video-queue')
        self.linkPads('video-queue', 'src', 'mpeg2subt', 'video')
        self.link('mpeg2subt', 'ffmpegcolorspace')
        self.link('ffmpegcolorspace', 'videoscale')
        self.link('videoscale', 'videosink')

        self.ghostify('mpeg2dec', 'sink', 'video')
        self.ghostify('mpeg2subt', 'subtitle', 'subtitle')


class BackPlayer(Bin):
    """The backend playback element that reads material from the DVD
    disk, demultiplexes it, and feeds to the front-end playback
    elements."""

    __slots__ = ()

    def __init__(self, options, name='backplayer'):
        super(BackPlayer, self).__init__(name)

        src = self.makeSubelem('dvdblocksrc', location=options['location'])
        demux = self.makeSubelem('dvddemux')

        self.link('dvdblocksrc', 'dvddemux')

        self.ghostify('dvddemux', 'current_video', 'video')
        self.ghostify('dvddemux', 'current_subpicture', 'subtitle')
        self.ghostify('dvddemux', 'current_audio', 'audio')

    def getBlockSource(self):
        return self.get_by_name('dvdblocksrc')


class Pipeline(gst.Pipeline):
    """The GStreamer pipeline used to play DVDs."""

    __slots__ = ('backPlayer',
                 'audioSink', 
                 'videoSink',
                 'syncHandlers')

    def __init__(self, options, name="dvdplayer"):
        super(Pipeline, self).__init__(name)

        # Build the pipeline.

        # The back player.
        self.backPlayer = BackPlayer(options)
        self.add(self.backPlayer)

#         self.videoSink = MySink()
#         self.add(self.videoSink)
#         self.backPlayer.link_pads('video', self.videoSink, 'sink')

        # The video playback element.
        self.videoSink = SoftwareVideo(options)
        self.add(self.videoSink)

#         self.audioSink = gst.element_factory_make('filesink', 'audiosink')
#         self.audioSink.set_property('location', 'sound.out')
#         self.audioSink = MySink()

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

        # A list of functions to synchronously handle bus messages.
        self.syncHandlers = []

        # Install a synchronous message handler to run the functions
        # in self.syncHandlers.
        self.get_bus().set_sync_handler(self.syncHandler)


    #
    # Bus Handling
    #

    def syncHandler(self, *args):
        try:
            for handler in self.syncHandlers:
                ret = handler(*args)
                if ret != None:
                    return ret
        except:
            gst.warning('Handler raised exception')

        return gst.BUS_PASS

    def addSyncBusHandler(self, handler):
        self.syncHandlers.append(handler)

    def removeSyncBusHandler(self, handler):
        self.syncHandlers.remove(handler)


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


