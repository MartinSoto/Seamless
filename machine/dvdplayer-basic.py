import sys
import string

from gobject import GObject
from gst import *

from player import *


#
# Main DVD Player Class
#

def sinkFromSpec(spec):
    sink = parse_launch(spec)
    sink.add_ghost_pad(sink.get_by_name('queue').get_pad('sink'),
                       'sink')
    return sink


class DVDPlayer(Thread):
    """
    """

    def __init__(self, name, location="/dev/dvd"):
        Thread.__init__(self, name)

        # Create an info object for the DVD.
        self.info = DVDInfo(location)

        # Build the pipeline.
        self.src = Element('dvdblocksrc', 'dvdblocksrc')
        self.add(self.src)

        self.demux = Element('dvddemux', 'dvddemux')
        self.add(self.demux)

        self.videoSink = sinkFromSpec("""
          { queue name=queue max-size-buffers=600 !
            dxr3videosink }
            """)
        self.add(self.videoSink)

        self.audioSink = sinkFromSpec("""
          { queue name=queue !
            ac3iec958 name=ac3iec958 !
            alsaspdifsink name=alsaspdifsink }
            """)
        self.add(self.audioSink)

        self.subpictureSink = sinkFromSpec("""
          { queue name=queue !
            dxr3spusink name=dxr3spusink }
            """)
        self.add(self.subpictureSink)

        self.src.link(self.demux)
        self.demux.link_pads('current_video', self.videoSink, 'sink')
        self.demux.link_pads('current_audio', self.audioSink, 'sink')
        self.demux.link_pads('current_subpicture', self.subpictureSink, 'sink')

        # Wrap the source element in a basic player.
        self.basicPlayer = BasicPlayer(self.src)

    def __getattr__(self, name):
        # Make this object a proxy for the basic player.
        return getattr(self.basicPlayer, name)

    def start(self):
        self.set_state(STATE_PLAYING)

    def stop(self):
        self.set_state(STATE_NULL)
