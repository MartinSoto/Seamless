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
import pipelineops as ops


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
                 'lock')


    def __init__(self, src, machine):
        self.src = src
        self.machine = machine

        self.mainItr = iter(self.machine)

        # The synchronized method lock.
        self.lock = threading.RLock()

        # Connect our signals to the source object.
        src.connect('vobu-read', self.vobuRead)
        src.connect('vobu-header', self.vobuHeader)


    #
    # Source Signal Handling
    #

    @synchronized
    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU."""

        try:
            # Get the next item.
            item = self.mainItr.next()
        except StopIteration:
            # Time to stop the pipeline.
            self.src.set_eos()
            self.src.emit('push-event', events.eosEvent())
            return
        except:
            # We had an exception in the playback code.
            traceback.print_exc()
            sys.exit(1)

        if isinstance(item, gst.Event):
            # We have an event, put it in the pipeline.
            self.src.emit('push-event', item);
        elif item == ops.machineStill:
            # We are displaying a still frame. Keep the pipeline busy,
            # but be nice to the processor:

            # We don't want to keep the lock while sleeping.
            self.lock.release()
            time.sleep(0.1)
            self.lock.acquire()

            self.src.emit('push-event', events.fillerEvent())

            return
        else:
            # Otherwise, we have a new playback position.
            (domain, titleNr, sectorNr) = item
            src.set_property('domain', domain)
            src.set_property('title', titleNr)
            src.set_property('vobu-start', sectorNr)

    @synchronized
    def vobuHeader(self, src, buf):
        """The signal handler for the source's vobu-header signal."""
        # This must be done inmediatly. Otherwise, the contents of the
        # buffer may change before we handle them.
        nav = dvdread.NavPacket(buf.get_data())

        # Send a nav event.
        self.src.emit('push-event', events.navEvent(nav.startTime,
                                                    nav.endTime))

        # Register the nav packet with the machine.
        self.machine.call(self.machine.setCurrentNav(nav))


    #
    # Interactive Operation Support
    #

    @synchronized
    def runEntryPoint(self, itr):
        """Run the specified iterator as entry point.

        The iterator will be run as the main iterator from a new
        iterator scheduler (itersched). The results can be either
        events, that will be sent immediately down the pipeline, or
        the 'defer' token. If the 'defer()' method is called, the
        execution is suspended and the iterator is moved to the top of
        the standard iterator scheduler."""
        sched = itersched.Scheduler(itr)
        for item in sched:
            if isinstance(item, ops.Defer):
                # Defer execution until next main loop iteration.
                self.machine.call(sched)
                return

            assert isinstance(item, gst.Event), \
                   "Spurious object '%s'" % str(item)
            self.src.emit('queue-event', item)

    def stopSource(self):
        """Stop the source element instantly."""
        self.src.set_property('block-count', 0)

    def defer(self):
        """When called by an entry point, transfers execution of the
        rest of the method to the main scheduler."""
        self.stopSource()
        yield ops.deferToken

    def flush(self):
        """Flush the pipeline."""
        yield events.flushEvent()

        # FIXME: Clean this up.
        programChain = self.machine.currentProgramChain()
        if programChain != None:
            yield events.subpictureClutEvent(programChain.clut)


    #
    # Pipeline Control
    #

    def setAudio(self, phys):
        """Set the physical audio stream to 'phys'."""
        pass

    def setSubpicture(self, phys):
        """Set the physical subpicture stream to 'phys'."""
        pass

    
