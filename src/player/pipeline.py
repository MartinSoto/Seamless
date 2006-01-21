# Seamless DVD Player
# Copyright (C) 2004-2006 Martin Soto <martinsoto@users.sourceforge.net>
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

import gobject

import gst

# Load private GStreamer plugins.
import loadplugins


class PipelineParseError(Exception):
    pass


class Bin(gst.Bin):
    """An enhanced GStreamer bin."""

    __slots__ = ()

    def makeSubelem(self, type, name=None, **keywords):
        if name == None:
            name = type

        subelem = gst.element_factory_make(type, name)

        self.addSubelem(subelem, **keywords)

    def makeParsedSubelem(self, descr, name=None, **keywords):
        if name == None:
            name = type

        try:
            subelem = gst.parse_launch(descr)
        except gobject.GError, e:
            raise PipelineParseError(
                _("Error parsing GStreamer pipeline '%s': %s") %
                (descr, str(e)))

        subelem.set_property('name', name)

        self.addSubelem(subelem, **keywords)

    def addSubelem(self, subelem, **keywords):
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

    #
    # Flush handling
    #

    def prepareFlush(self):
        pass

    def closeFlush(self):
        pass


class SoftwareAudio(Bin):
    """An audio playback element that uses software decoders for AC3
    and DTS."""

    __slots__ = ('clock')

    def __init__(self, options, name='audiodec'):
        super(SoftwareAudio, self).__init__(name)

        self.makeSubelem('capsselect')

        # The AC3 decoding pipeline.
        self.makeSubelem('a52dec')
        self.makeSubelem('audioconvert', 'audioconvert1')
        self.makeSubelem('audioresample', 'audioresample1')
        
        # The LPCM decoding pipeline.
        self.makeSubelem('dvdlpcmdec')
        self.makeSubelem('audioconvert', 'audioconvert2')
        self.makeSubelem('audioresample', 'audioresample2')
        
        self.makeSubelem('capsaggreg')

        self.makeSubelem('queue', max_size_buffers=0, max_size_bytes=0,
                         max_size_time=gst.SECOND)
        self.makeParsedSubelem(options['audioSink'], 'audiosink')

        self.linkPads('capsselect', 'src%d', 'a52dec', 'sink')
        self.link('a52dec', 'audioconvert1')
        self.link('audioconvert1', 'audioresample1')
        self.linkPads('audioresample1', 'src', 'capsaggreg', 'sink%d')

        self.linkPads('capsselect', 'src%d', 'dvdlpcmdec', 'sink')
        self.link('dvdlpcmdec', 'audioconvert2')
        self.link('audioconvert2', 'audioresample2')
        self.linkPads('audioresample2', 'src', 'capsaggreg', 'sink%d')

        self.link('capsaggreg', 'queue')
        self.link('queue', 'audiosink')

        self.ghostify('capsselect', 'sink')


class SpdifAudio(Bin):
    """An audio playback element that feeds AC3 sound (DTS coming
    soon) to an external hardware decoder through an SP/DIF digital
    audio interface. The SP/DIF device is driven using ALSA."""

    __slots__ = ('clock')

    def __init__(self, options, name='audiodec'):
        super(SpdifAudio, self).__init__(name)

        self.makeSubelem('capsselect')

        # The AC3 decoding pipeline. The capsfilter elements are
        # necessary to work around a bug in (apparently) alsasink.
        self.makeSubelem('ac3iec958', raw_audio=True)
        self.makeSubelem('capsfilter', 'capsfilter1',
                         caps=gst.Caps('audio/x-raw-int,'
                                       'endianness = (int) 4321,'
                                       'signed = (boolean) true,'
                                       'width = (int) 16,'
                                       'depth = (int) 16,'
                                       'rate = (int) 48000,'
                                       'channels = (int) 2'))
        self.makeSubelem('audioconvert', 'audioconvert1')
        self.makeSubelem('capsfilter', 'capsfilter2',
                         caps=gst.Caps('audio/x-raw-int,'
                                       'endianness = (int) 1234,'
                                       'signed = (boolean) true,'
                                       'width = (int) 16,'
                                       'depth = (int) 16,'
                                       'rate = (int) 48000,'
                                       'channels = (int) 2'))
        
        # The LPCM decoding pipeline.
        self.makeSubelem('dvdlpcmdec')
        self.makeSubelem('audioconvert', 'audioconvert2')
        self.makeSubelem('audioresample', 'audioresample2')
        
        self.makeSubelem('capsaggreg')

        # Apparently, this queue can get confused and accept too much
        # material if limited only by time. Fortunately, we can also
        # limit it to 1s material by size.
        self.makeSubelem('queue', max_size_buffers=0, max_size_bytes=192000,
                         max_size_time=gst.SECOND)
        self.makeSubelem(options['audioSink'], 'audiosink',
                         device='spdif:{AES0 0x0 AES1 0x82 AES2 0x0 '
                         'AES3 0x2 CARD %(spdifCard)s}' % options)

        self.linkPads('capsselect', 'src%d', 'ac3iec958', 'sink')
        self.link('ac3iec958', 'capsfilter1')
        self.link('capsfilter1', 'audioconvert1')
        self.link('audioconvert1', 'capsfilter2')
        self.linkPads('capsfilter2', 'src', 'capsaggreg', 'sink%d')

        self.linkPads('capsselect', 'src%d', 'dvdlpcmdec', 'sink')
        self.link('dvdlpcmdec', 'audioconvert2')
        self.link('audioconvert2', 'audioresample2')
        self.linkPads('audioresample2', 'src', 'capsaggreg', 'sink%d')

        self.link('capsaggreg', 'queue')
        self.link('queue', 'audiosink')

        self.ghostify('capsselect', 'sink')


class SoftwareVideo(Bin):
    """A video playback element that decodes MPEG2 video using a
    software decoder."""

    __slots__ = ()

    def __init__(self, options, name='videodec'):
        super(SoftwareVideo, self).__init__(name)

        self.makeSubelem('mpeg2dec')
        self.makeSubelem('queue', 'video-queue',
                         max_size_buffers=0, max_size_bytes=0,
                         max_size_time=gst.SECOND)

        # In order to guarantee quick interactive response, buffering
        # between the subtitle decoder and the video sink should be as
        # limited as possible.
        self.makeSubelem('mpeg2subt')
        self.makeSubelem('ffmpegcolorspace')
        self.makeSubelem('videoscale')
        self.makeSubelem('dvdaspect')

        # A (usually) one-frame queue whose size is increased before
        # flushing and reduced again short thereafter. See "flush
        # handling" for details.
        self.makeSubelem('queue', 'frame-queue',
                         max_size_buffers=1, max_size_bytes=0,
                         max_size_time=0)
        self.makeParsedSubelem(options['videoSink'], 'videosink',
                               force_aspect_ratio=True,
                               pixel_aspect_ratio=options['pixelAspect'])

        self.link('mpeg2dec', 'video-queue')
        self.linkPads('video-queue', 'src', 'mpeg2subt', 'video')
        self.link('mpeg2subt', 'ffmpegcolorspace')
        self.link('ffmpegcolorspace', 'videoscale')
        self.link('videoscale', 'dvdaspect')
        self.link('dvdaspect', 'frame-queue')
        self.link('frame-queue', 'videosink')

        self.ghostify('mpeg2dec', 'sink', 'video')
        self.ghostify('mpeg2subt', 'subtitle', 'subtitle')

    #
    # Flush handling
    #

    def prepareFlush(self):
        """Prepare the video bin for a flush operation."""
        # When entering a menu, it is often the case that highlights
        # are changed by the DVD machine many times in a short
        # progresion. Each one of these changes forces the subtitle
        # decoder to produce a new frame. When the DVD enters the menu
        # directly after a flush, these video frames can cause a
        # pipeline deadlock because they often arrive before any audio
        # has been sent, but the lack of audio means that the pipeline
        # is still prerolling and cannot process more video.

        # We increase the size of the frame queue to allow for enough
        # frames to be queued that prerolling is possible and playback
        # can continue.
        self.get_by_name('frame-queue').set_property('max-size-buffers', 15)

    def closeFlush(self):
        """Prepare the video bin for running after a flush."""
        # Reduce the size of the frame queue to one frame, to increase
        # interactive responsiveness.
        self.get_by_name('frame-queue').set_property('max-size-buffers', 1)



class BackPlayer(Bin):
    """The backend playback element that reads material from the DVD
    disk, demultiplexes it, and feeds to the front-end playback
    elements."""

    __slots__ = ()

    def __init__(self, options, name='backplayer'):
        super(BackPlayer, self).__init__(name)

        self.makeSubelem('dvdblocksrc', location=options['location'])
        self.makeSubelem('dvddemux')
        self.makeSubelem('audiofiller')

        self.link('dvdblocksrc', 'dvddemux')
        self.linkPads('dvddemux', 'current_audio', 'audiofiller', 'sink')

        self.ghostify('dvddemux', 'current_video', 'video')
        self.ghostify('dvddemux', 'current_subpicture', 'subtitle')
        self.ghostify('audiofiller', 'src', 'audio')

    def getBlockSource(self):
        return self.get_by_name('dvdblocksrc')


class Pipeline(gst.Pipeline):
    """The GStreamer pipeline used to play DVDs."""

    __slots__ = ('backPlayer',
                 'audioBin',
                 'videoBin',
                 'syncHandlers')

    def __init__(self, options, name="dvdplayer"):
        super(Pipeline, self).__init__(name)

        # Build the pipeline.

        # The back player.
        self.backPlayer = BackPlayer(options)
        self.add(self.backPlayer)

        # The video playback element.
        self.videoBin = SoftwareVideo(options)
        self.add(self.videoBin)

        # The audio playback element.
        if options.spdifCard:
            self.audioBin = SpdifAudio(options)
        else:
            self.audioBin = SoftwareAudio(options)
        self.add(self.audioBin)

        # All together now.
        self.backPlayer.link_pads('video', self.videoBin, 'video')
        self.backPlayer.link_pads('subtitle', self.videoBin, 'subtitle')
        self.backPlayer.link_pads('audio', self.audioBin, 'sink')

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
        return self.videoBin.get_by_name('videosink')


    #
    # Flush handling
    #

    def prepareFlush(self):
        """Prepare the pipeline for a flush operation."""
        self.videoBin.prepareFlush()
        self.audioBin.prepareFlush()

    def closeFlush(self):
        """Prepare the pipeline for running after a flush."""
        self.videoBin.closeFlush()
        self.audioBin.closeFlush()
