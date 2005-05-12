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
import pipelinecmds as cmds


def interactiveOp(method):
    """Turns an `itersched` runnable generator method into an
    interactive operation, that will be executed as soon as possible
    on the pipeline. Any class using this decorator must have a
    `pipeline`attribute pointing to an adeuate `Pipeline`instance.

    `method` will be wrapped to be run using the `runInteractive`
    method in the pipeline object."""
    def wrapper(self, *args, **keywords):
        self.pipeline.runInteractive(method(self, *args, **keywords))

    return wrapper


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
    """The object in charge of managing the playback pipeline.

    The playback pipeline reads material from the disc and processes
    it by demultiplexing it and sending the resulting streams to the
    appropriate decoding and display elements. It is also responsible
    for mixing the subtitles and menu highlights into the video.

    The actual sequence in which material is read from the disc, as
    well as the selection of video, audio and subtitle streams and the
    activation of highlights are controlled by the DVD virtual
    machine. In this implementation, the virtual machine produces a
    sequence of command objects (as an iterator) that, when invoked
    with the pipeline as parameter, perform the required operations
    The machine is restricted to use the operations defined in module
    'pipelinecmds'.

    The `PlayVobu` operation is particularly important, since it is
    used by the machine to tell the pipeline which VOBU from the disk
    to play next. After receiving a `PlayVobu` the pipeline reads the
    header (navigation packet) of the specified VOBU, and hands it to
    the machine using the `setCurrentNav` method. After that, it reads
    one single operation from the machine and executes it
    immediatly. This is done in order to give the machine a chance of
    analyzing the header and, if necessary, skipping the playback of
    the VOBU. To skip the VOBU, the machine can send the `cancelVobu`
    operation. Otherwise, it should sent a `DoNothing` operation.

    One important task of this class is to determine, in an automatic
    and reliable way, when a flush operation should be triggered. The
    problem is that a flush is only necessary when the machine
    activates certain actions as the result of an interactive
    operation (only interactive operations require breaking the flow
    of playback). A sizeable portion of the logic is devoted to
    that. Basically, commands are read from the machine and collected
    until it is clear whether the interactive operation was completed,
    or a flush-requiring operation was triggered."""

    __slots__ = ('src',
                 'machine',
                 'mainItr',
                 'lock',

                 'audio',
                 'subpicture',
                 'clut',
                 'area',
                 'button',
                 'palette',

                 'pendingCmds',
                 'immediate')


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

        # A list of pipeline commands that where already read from the
        # machine, but haven't yet been executed.
        self.pendingCmds = []

        # If true, events will be sent directly down the pipeline,
        # instead of being queued in the source element.
        self.immediate = False

    def sendEvent(self, event):
        """Send `event` down the pipeline."""
        if self.immediate:
            self.src.emit('push-event', event)
        else:
            self.src.emit('queue-event', event)


    #
    # Source Signal Handling
    #

    def collectCmds(self):
        """Collect commands."""
        events = []
        for cmd in self.mainItr:
            events.append(cmd)
            if isinstance(cmd, cmds.PlayVobu) or \
                   isinstance(cmd, cmds.Pause) or \
                   isinstance(cmd, self.EndInteractive):
                return events

        return events

    @synchronized
    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU."""

        self.immediate = True

        try:
            if self.pendingCmds == []:
                cmds = self.collectCmds()
            else:
                cmds = self.pendingCmds
                self.pendingCmds = []

            if cmds == []:
                # Time to stop the pipeline.
                self.src.set_eos()
                self.src.emit('push-event', events.eos())
                return

            for cmd in cmds:
                # Execute the command on the pipeline.
                cmd(self)
        except:
            # We had an exception in the playback code.
            traceback.print_exc()
            sys.exit(1)

        self.immediate = False

    @synchronized
    def vobuHeader(self, src, buf):
        """The signal handler for the source's vobu-header signal."""
        # Release the lock set by the playVobu operation.
        self.lock.release()

        # Create a nav packet object.
        nav = dvdread.NavPacket(buf.get_data())

        # Hand the packet to the machine.
        self.machine.setCurrentNav(nav)

        # Read the confirm/cancel operation and execute it.
        self.mainItr.next()(self)

        if self.src.get_property('block-count') == 0:
            # VOBU playback was cancelled.
            return

        # Send a nav event.
        self.src.emit('push-event', events.nav(nav.startTime,
                                               nav.endTime))

        # FIXME: This should be done later in the game, namely, when
        # the packet actually reaches the subtitle element.
        self.machine.callIterator(self.machine.setButtonNav(nav))


    #
    # Interactive Operation Support
    #

    class EndInteractive(cmds.DoNothing):
        """A do nothing command, used to mark the end of an
        interactive operation."""
        __slots__ = ()


    @synchronized
    def runInteractive(self, itr):
        """Run `itr` interactively.

        `itr` must be an `itersched` runnable iterator, that returns a
        sequence of machine control command objects. Based on the
        commands produced, this method decides automatically between
        executing the commands immediatly (asynchronously from the
        machine's main loop) or flushing the pipeline and letting the
        main machine's loop do the work. In any case, the commands are
        expected to be executed as soon as possible, thus providing a
        reasonable interactive response.

        The `interactiveOp' decorator can be used to have a method be
        executed through this mechanism.
        """
        
        def op():
            """Call the iterator and send an `EndInteractive`
            operation at the end."""
            yield itersched.Call(itr)
            yield self.EndInteractive()

        self.machine.callIterator(op())

        cmds = self.collectCmds()

        if cmds != [] and isinstance(cmds[-1], self.EndInteractive):
            # We saw the end of the interactive operation before
            # reaching any VOBU playback operation. Commands should be
            # executed right now without flushing.
            for cmd in cmds:
                cmd(self)
        else:
            # We reached a VOBU playback operation while doing the
            # interactive operation. Flush and go on.
            self.cancelVobu()
            cmds[0:0] = [Pipeline.flush]
            self.pendingCmds = cmds


    #
    # Pipeline Control
    #

    def playVobu(self, domain, titleNr, sectorNr):
        """Set the source element to play the VOBU corresponding to
        'domain', 'titleNr', and 'sectorNr'."""
        self.src.set_property('domain', domain)
        self.src.set_property('title', titleNr)
        self.src.set_property('vobu-start', sectorNr)

        # Acquire the lock until the header arrives. An interactive
        # operation arriving in the middle could cause real
        # devastation.
        self.lock.acquire()

    def cancelVobu(self):
        """Cancel the playback of the current VOBU.

        This forces the source to immediatly ask for more work by
        firing the `vobu-read` singnal."""
        # Setting the current block count to 0 does the trick.
        self.src.set_property('block-count', 0)

    def setAudio(self, phys):
        """Set the physical audio stream to 'phys'."""
        if self.audio == phys:
            return
        self.audio = phys

        self.sendEvent(events.audio(self.audio))

    def setSubpicture(self, phys):
        """Set the physical subpicture stream to 'phys'."""
        if self.subpicture == phys:
            return
        self.subpicture = phys

        self.sendEvent(events.subpicture(self.subpicture))

    def setSubpictureClut(self, clut):
        """Set the subpicture color lookup table to 'clut'.

        'clut' is a 16-position array."""
        if self.clut == clut:
            return
        self.clut = clut

        self.sendEvent(events.subpictureClut(self.clut))

    def highlight(self, area, button, palette):
        """Highlight the specified area, corresponding to the
        specified button number and using the specified palette."""
        if (area, button, palette) == \
           (self.area, self.button, self.palette):
            return
        (self.area, self.button, self.palette) = (area, button, palette)

        self.sendEvent(events.highlight(self.area,
                                         self.button,
                                         self.palette))

    def resetHighlight(self):
        """Clear (reset) the highlighted area."""
        # Asking for area is enough.
        if self.area == None:
            return
        (self.area, self.button, self.palette) = (None, None, None)

        self.sendEvent(events.highlightReset())

    def stillFrame(self):
        """Tell the pipeline that a still frame was sent."""
        self.sendEvent(events.eos())

    def flush(self):
        """Flush the pipeline."""
        self.sendEvent(events.flush())

        # A flush erases the CLUT. Restore it.
        self.sendEvent(events.subpictureClut(self.clut))

        # Reset the highlight state.
        self.area = None
        self.button = None
        self.palette = None

    def pause(self):
        """Pause the pipeline for a short time (currently 0.1s).

        Warning: This method temporarily releases the object's lock"""
        self.sendEvent(events.filler())

        # We don't want to keep the lock while sleeping.
        self.lock.release()
        time.sleep(0.1)
        self.lock.acquire()

    def eos(self):
        """Signal the end of stream (EOS) to the pipeline."""
        self.sendEvent(events.eos())

