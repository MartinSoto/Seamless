import gobject
try:
    gobject.threads_init()
except:
    print "WARNING: gobject doesn't have threads_init, no threadsafety"

from gst import *

import plugin

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

    def __init__(self, name, location="/dev/dvd"):
        Thread.__init__(self, name)

        # Create an info object for the DVD.
        self.info = DVDInfo(location)

        # Build the pipeline.

        #timeout = "timeout=10000000"
        timeout = ""
        self.dvdSrc = parse_launch("""
        (
          dvdblocksrc name=dvdblocksrc !
            dvddemux name=dvddemux .current_video !
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
          mpeg2subt name=mpeg2subt !
            xvimagesink name=videosink brightness=50 hue=1000
        }
        """)
        ghostify(self.videoSink, 'mpeg2subt', 'video')
        ghostify(self.videoSink, 'mpeg2subt', 'subtitle')
        self.videoSinkElem = self.videoSink.get_by_name('videosink')
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
            alsaspdifsink name=audiosink
        }
        """)
        ghostify(self.audioSink, 'ac3iec958', 'sink', 'audio')
        self.audioSinkElem = self.audioSink.get_by_name('audiosink')
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


    def identHandoff(self, object, buffer):
        #print object.get_name()
        pass


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
