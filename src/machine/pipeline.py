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
import threading
import traceback
import sys

import gst

import itersched

import dvdread
import events


def synchronized(method):
    """Decorator for syncronized methods."""

    def wrapper(self, *args, **keywords):
        self.lock.acquire()
        try:
            method(self, *args, **keywords)
        finally:
            self.lock.release()

    return wrapper

class Pipeline(object):
    """The object in charge of managing the playback pipeline."""

    __slots__ = ('src',
                 'machine',
                 'mainItr',
                 'lock',

                 'audio',
                 'subpicture',
                 'clut',
                 'area',
                 'button',
                 'palette')


    def __init__(self, src, machine):
        self.src = src
        self.machine = machine

        self.mainItr = iter(self.machine)

        # The synchronized method lock.
        self.lock = threading.RLock()

        # Connect our signals to the source object.
        src.connect('vobu-read', self.vobuRead)
        src.connect('vobu-header', self.vobuHeader)

        # Initialize the pipeline state variables:
        self.audio = None
        self.subpicture = None
        self.clut = None
        self.area = None
        self.button = None
        self.palette = None

    #
    # Utility Methods
    #

    def queueEvent(self, event):
        """Put 'event' in the source's queue."""
        self.src.emit('queue-event', event)

    def stopSource(self):
        """Stop the source element instantly."""
        self.src.set_property('block-count', 0)



    #
    # Source Signal Handling
    #

    @synchronized
    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU."""

        try:
            # Get the next command object.
            cmd = self.mainItr.next()
        except StopIteration:
            # Time to stop the pipeline.
            self.src.set_eos()
            self.src.emit('push-event', events.eos())
            return
        except:
            # We had an exception in the playback code.
            traceback.print_exc()
            sys.exit(1)

        # Execute the command on the pipeline.
        cmd(self)

    @synchronized
    def vobuHeader(self, src, buf):
        """The signal handler for the source's vobu-header signal."""
        # This must be done inmediatly. Otherwise, the contents of the
        # buffer may change before we handle them.
        nav = dvdread.NavPacket(buf.get_data())

        # Send a nav event.
        self.src.emit('push-event', events.nav(nav.startTime,
                                               nav.endTime))

        # Register the nav packet with the machine.
        self.machine.call(self.machine.setCurrentNav(nav))


    #
    # Interactive Operation Support
    #

    class Defer(object):
        """A special token used internally to mark the end of the
        immediate part of an entry point."""
        __slots__ = ()

    deferToken = Defer()
    """A single instance of the 'Defer' class."""

    @synchronized
    def runEntryPoint(self, itr):
        """Run the specified iterator as entry point.

        The iterator will be run as the main iterator from a new
        iterator scheduler (itersched). The iterator results must be
        pipeline commands, and will be executed immediately, unless
        'defer()' is used. If the 'defer()' method is called using
        itersched's 'Call' operation, the execution will be suspended
        and the iterator will be moved to the top of the machine's
        iterator scheduler to continue executing there."""
        sched = itersched.Scheduler(itr)
        for cmd in sched:
            if isinstance(cmd, self.Defer):
                # Defer execution until next main loop iteration.
                self.machine.call(sched)
                return

            # Execute the command on the pipeline.
            cmd(self)

    def defer(self):
        """When called (using itersched's 'Call') by an entry point,
        transfers execution of the rest of the method to the machine
        scheduler."""
        self.stopSource()
        yield self.deferToken


    #
    # Pipeline Control
    #

    def playVobu(self, domain, titleNr, sectorNr):
        """Play the VOBU corresponding to 'domain', 'titleNr', and
        'sectorNr'."""
        self.src.set_property('domain', domain)
        self.src.set_property('title', titleNr)
        self.src.set_property('vobu-start', sectorNr)

    def setAudio(self, phys):
        """Set the physical audio stream to 'phys'."""
        if self.audio == phys:
            return
        self.audio = phys

        self.queueEvent(events.audio(self.audio))

    def setSubpicture(self, phys):
        """Set the physical subpicture stream to 'phys'."""
        if self.subpicture == phys:
            return
        self.subpicture = phys

        self.queueEvent(events.subpicture(self.subpicture))

    def setSubpictureClut(self, clut):
        """Set the subpicture color lookup table to 'clut'.

        'clut' is a 16-position array."""
        if self.clut == clut:
            return
        self.clut = clut

        self.queueEvent(events.subpictureClut(self.clut))

    def highlight(self, area, button, palette):
        """Highlight the specified area, corresponding to the
        specified button number and using the specified palette."""
        if (area, button, palette) == \
           (self.area, self.button, self.palette):
            return
        (self.area, self.button, self.palette) = (area, button, palette)

        self.queueEvent(events.highlight(self.area,
                                         self.button,
                                         self.palette))

    def resetHighlight(self):
        """Clear (reset) the highlighted area."""
        # Asking for area is enough.
        if self.area == None:
            return
        (self.area, self.button, self.palette) = (None, None, None)

        self.queueEvent(events.highlightReset())

    def stillFrame(self):
        """Tell the pipeline that a still frame was sent."""
        self.queueEvent(events.eos())

    def flush(self):
        """Flush the pipeline."""
        self.queueEvent(events.flush())

        # A flush erases the CLUT.
        self.queueEvent(events.subpictureClut(self.clut))

    def pause(self):
        """Pause the pipeline for a short time (currently 0.1s)."""
        # We don't want to keep the lock while sleeping.
        self.lock.release()
        time.sleep(0.1)
        self.lock.acquire()

        self.queueEvent(events.filler())

    def eos(self):
        """Signal the end of stream (EOS) to the pipeline."""
        self.queueEvent(events.eos())

