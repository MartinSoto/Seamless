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
from sig import SignalHolder, signal

import dvdread
import events
import machine


def interactiveOp(method):
    """Turns an `itersched` runnable generator method into an
    interactive operation, that will be executed as soon as possible
    on the pipeline. Any class using this decorator must have a
    `manager`attribute pointing to an adequate `Manager` instance.

    `method` will be wrapped to be run using the `runInteractive`
    method in the pipeline object."""
    def wrapper(self, *args, **keywords):
        self.manager.runInteractive(method(self, *args, **keywords))

    wrapper.__name__ = method.__name__
    return wrapper


def synchronized(method):
    """Decorator for syncronized methods."""

    def wrapper(self, *args, **keywords):
        self.lock.acquire()
        try:
            method(self, *args, **keywords)
        finally:
            self.lock.release()

    wrapper.__name__ = method.__name__
    return wrapper


class Manager(SignalHolder):
    """The object in charge of managing the interaction between the
    machine and the playback pipeline.

    The playback pipeline reads material from the disc and processes
    it by demultiplexing it and sending the resulting streams to the
    appropriate decoding and display elements. It is also responsible
    for mixing the subtitles and menu highlights into the video.

    The actual sequence in which material is read from the disc, as
    well as the selection of video, audio and subtitle streams and the
    activation of highlights are controlled by the DVD virtual
    machine. In this implementation, the virtual machine produces a
    sequence of command objects (as an iterator) that, when invoked
    with the manager as parameter, perform the required operations.
    The machine is restricted to use the operations defined in the
    `machine` module.

    The `PlayVobu` operation is particularly important, since it is
    used by the machine to tell the pipeline which VOBU from the disk
    to play next. After receiving a `PlayVobu` the pipeline reads the
    header (navigation packet) of the specified VOBU, and hands it to
    the machine using the `setCurrentNav` method. After that, it reads
    one single operation from the machine and executes it
    immediatly. This is done in order to give the machine a chance of
    analyzing the header and, if necessary, skipping the playback of
    the VOBU. To skip the VOBU, the machine can send the `cancelVobu`
    operation. Otherwise, it should send a `DoNothing` operation.

    One important task of this class is to determine, in an automatic
    and reliable way, when a flush operation should be triggered. The
    problem is that a flush is only necessary when the machine
    activates certain actions as the result of an interactive
    operation (only interactive operations require breaking the flow
    of playback). A sizeable portion of the logic is devoted to
    that. Basically, commands are read from the machine and collected
    until it is clear whether the interactive operation was completed,
    or a flush-requiring operation was triggered."""

    __slots__ = ('pipeline',
                 'machine',

                 'src',
                 'srcPad',
                 'mainItr',
                 'lock',

                 'audio',
                 'subpicture',
                 'subpictureHide',
                 'clut',
                 'area',
                 'button',
                 'palette',

                 'pendingCmds',
                 'interactiveCount',
                 'vobuReadReturn',

                 'segmentStart',
                 'segmentStop',

                 'flushing')


    def __init__(self, machine, pipeline):
        self.machine = machine
        self.pipeline = pipeline

        self.src = pipeline.getBlockSource()
        self.srcPad = self.src.get_pad('src')

        # A bus message handler for the flush operation.
        self.pipeline.get_bus().add_watch(self.flushMsgHandler)

        self.mainItr = iter(self.machine)

        # The synchronized method lock.
        self.lock = threading.RLock()

        # Connect our signals to the source object.
        self.src.connect('vobu-read', self.vobuRead)
        self.src.connect('vobu-header', self.vobuHeader)

        # Initialize the manager state variables:
        self.audio = None
        self.subpicture = None
        self.subpicture = False
        self.clut = None
        self.area = None
        self.button = None
        self.palette = None

        # A list of machine commands that where already read from the
        # machine, but haven't yet been executed.
        self.pendingCmds = []

        # A counter that increments itself whenever an interactive
        # operation is executed. It is used to deal with call/resume
        # operations and pipeline flushing.
        self.interactiveCount = 0

        # Start and stop times of the current segment. The current
        # segment covers the current VOBU and all preceeding VOBUs
        # contiguous in time.
        self.segmentStart = None
        self.segmentStop = None

        self.flushing = False

    def sendEvent(self, event):
        """Send `event` down the pipeline."""
        self.srcPad.push_event(event)


    #
    # Source Signal Handling
    #

    def collectCmds(self):
        """Collect commands."""
        events = []
        for cmd in self.mainItr:
            events.append(cmd)
            if isinstance(cmd, machine.PlayVobu) or \
               isinstance(cmd, machine.Pause) or \
               (isinstance(cmd, self.EndInteractive) and
                cmd.count == self.interactiveCount):
                return events

        return events

    @synchronized
    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU."""
        gst.debug("Vobu read")

        # Commands expecting this method to return set vobuReadReturn
        # to True.
        self.vobuReadReturn = False

        try:
            while not self.vobuReadReturn:
                if self.pendingCmds == []:
                    cmds = self.collectCmds()
                else:
                    cmds = self.pendingCmds
                    self.pendingCmds = []

                if cmds == []:
                    # Time to stop the pipeline.
                    break

                while cmds:
                    # Execute the command on the pipeline.
                    gst.debug("Running command %s" % str(cmds[0]))
                    cmds[0](self)
                    cmds[0:1] = []

                    if self.vobuReadReturn:
                        self.pendingCmds = cmds
                        break
        except:
            # We had an exception in the playback code.
            traceback.print_exc()
            sys.exit(1)

        gst.debug("VOBU read end")

    @synchronized
    def vobuHeader(self, src, buf):
        """The signal handler for the source's vobu-header signal."""
        gst.debug("Vobu header")

        # Release the lock set by the playVobu operation.
        self.lock.release()

        # Create a nav packet object.
        nav = dvdread.NavPacket(buf.data)

        # Hand the packet to the machine.
        self.machine.setCurrentNav(nav)

        # Read the confirm/cancel operation and execute it.
        cmd = self.mainItr.next()
        cmd(self)
        
        if isinstance(cmd, machine.CancelVobu):
            # VOBU playback was cancelled.
            return

        # Update the current segment and send a corresponding
        # newsegment event.
        start = events.mpegTimeToGstTime(nav.startTime)
        stop = events.mpegTimeToGstTime(nav.endTime)
        if self.segmentStop != start:
            # We have a new segment
            self.segmentStart = start
            self.segmentStop = stop
            update = False
            gst.debug('New current segment')
        else:
            # We have an update:
            self.segmentStop = stop
            update = True
            gst.debug('Current segment update')
        self.sendEvent(events.newsegment(update, self.segmentStart,
                                         self.segmentStop))

        # FIXME: This should be done later in the game, namely, when
        # the packet actually reaches the subtitle element.
        self.machine.callIterator(self.machine.setButtonNav(nav))



    #
    # Bus Message Handling
    #

    def flushMsgHandler(self, bus, msg):
        """Implements pipeline flushing by sending a flushing seek
        event from the application thread."""

        # Flush is started by a seamless.Flush bus message. We pause
        # the pipeline, send a seek event, and set the pipeline into
        # motion again.
        if msg.type & gst.MESSAGE_APPLICATION and \
               msg.structure.has_name('seamless.Flush'):
            # Flush message received, start flushing.
            self.pipeline.set_state(gst.STATE_PAUSED)

        elif self.flushing and \
                 msg.type & gst.MESSAGE_STATE_CHANGED and \
                 msg.src == self.pipeline:
            (old, new, pending) =  msg.parse_state_changed()

            if new == gst.STATE_PAUSED and \
                   pending == gst.STATE_VOID_PENDING:
                # The pipeline is paused.

                self.pipeline.prepareFlush()

                # Send the seek event and from a single sink element
                # to guarantee that it arrives only once to the
                # source.
                self.pipeline.getVideoSink().seek(1.0, gst.FORMAT_TIME,
                                                  gst.SEEK_FLAG_FLUSH,
                                                  gst.SEEK_TYPE_CUR, 0,
                                                  gst.SEEK_TYPE_NONE, -1)

                # Set the stream time to guarantee audio/video
                # synchronization.
                self.pipeline.set_new_stream_time(0L)

                # Go back to playing.
                self.pipeline.set_state(gst.STATE_PLAYING)

            elif new == gst.STATE_PLAYING and \
                     pending == gst.STATE_VOID_PENDING:
                # We are playing again, complete the flush operation.

                self.pipeline.closeFlush()
            
                self.flushing = False
                gst.debug("flush completed")

        return True


    #
    # Interactive Operation Support
    #

    class EndInteractive(machine.DoNothing):
        """A do nothing command, used to mark the end of an
        interactive operation. It carries the serial count of
        interactive operations stored in the pipeline."""
        __slots__ = ('count')


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

        # Theory of operation: we run the provided iterator inside a
        # wrapper, that calls the iterator and yields a special marker
        # (an object of class `EndInteractive`) afterwards. The
        # `collectCmds` method stops collecting on anything that means
        # displaying new video (a `PlayVobu` or `Pause` command) or on
        # `EndInteractive`. If the last element of the sequence
        # returned by `collectCmds` is an `EndInteractive` we know the
        # operation completed without attempting to jump anywhere
        # where new video is played and don't flush the
        # pipeline. Otherwise, we flush the pipeline before executing
        # the collected commands.
        #
        # There is a caveat, however: when an interactive operation
        # performs a DVD call operation, the wrapper remains in the
        # itersched stack, and will eventually return its
        # `EndInteractive` when the DVD machine does a resume. For
        # this reason, we put a consecutive count in the
        # `EndInteractive` objects and check it in `collectCmds` to
        # make sure that we are reacting to the right `EndInteractive`
        # command.

        if self.flushing:
            return

        def interactiveWrapper(count):
            """Call the iterator and send an `EndInteractive`
            operation at the end."""
            yield itersched.Call(itr)

            end = self.EndInteractive()
            end.count = count
            yield end

        gst.debug("run interactive")

        self.interactiveCount += 1

        # The end interactive marker carries the sequential count in
        # it. collectCmds matches this count with the current one.
        self.machine.callIterator(interactiveWrapper(self.interactiveCount))

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
            cmds[0:0] = [self.__class__.flush,
                         self.__class__.resendSubpictureClut]
            self.pendingCmds = cmds

        gst.debug("end run interactive")


    #
    # Pipeline Control
    #

    def playVobu(self, domain, titleNr, sectorNr):
        """Set the source element to play the VOBU corresponding to
        'domain', 'titleNr', and 'sectorNr'."""
        gst.debug("play vobu")

        self.src.set_property('domain', domain)
        self.src.set_property('title', titleNr)
        self.src.set_property('vobu-start', sectorNr)

        # Acquire the lock until the header arrives. An interactive
        # operation arriving in the middle could cause real
        # devastation.
        self.lock.acquire()

        self.vobuReadReturn = True

    def cancelVobu(self):
        """Cancel the playback of the current VOBU.

        This forces the source to immediatly ask for more work by
        firing the `vobu-read` singnal."""
        gst.debug("cancel VOBU")

        #self.src.set_property('cancel-vobu', True)

    def setAspectRatio(self, aspectRatio):
        """Set the display aspect ratio to `aspectRatio`.

        Emits the aspectRatioChanged signal."""
        gst.debug("set aspect ratio")

        if aspectRatio == machine.ASPECT_RATIO_4_3:
           self.aspectRatioChanged(4.0/3)
        elif aspectRatio == machine.ASPECT_RATIO_16_9:
            self.aspectRatioChanged(16.0/9)
        else:
            assert 0, "Invalid aspect ratio value"
        pass

    def setAudio(self, phys):
        """Set the physical audio stream to 'phys'."""
        gst.debug("set audio")

        if self.audio == phys:
            return
        self.audio = phys

        self.sendEvent(events.audio(self.audio))

    def setSubpicture(self, phys, hide):
        """Set the physical subpicture stream to `phys`.

        If `hide` is `True` the stream will be hidden and only shown
        when forced display is set by the SPU packet."""
        if self.subpicture == phys and self.subpictureHide == hide:
            return
        self.subpicture = phys
        self.subpictureHide = hide

        self.sendEvent(events.subpicture(self.subpicture))

        if self.subpictureHide:
             self.sendEvent(events.subpictureHide())
        else:
             self.sendEvent(events.subpictureShow())

    def setSubpictureClut(self, clut):
        """Set the subpicture color lookup table to 'clut'.

        'clut' is a 16-position array."""
        gst.debug("set subpicture CLUT")

        if self.clut == clut:
            return
        self.clut = clut

        self.sendEvent(events.subpictureClut(self.clut))

    def resendSubpictureClut(self):
        """Resend the subpicture color lookup table down the pipeline.

        This is needed after a flush."""
        gst.debug("resend subpicture CLUT")

        if self.clut != None:
            self.sendEvent(events.subpictureClut(self.clut))

    def highlight(self, area, button, palette):
        """Highlight the specified area, corresponding to the
        specified button number and using the specified palette."""
        gst.debug("highlight")

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
        gst.debug("still frame")

        self.sendEvent(events.stillFrame())

    def flush(self):
        """Flush the pipeline."""
        gst.debug("flush")
            
        # A flush erases the CLUT. Restore it.
        #self.sendEvent(events.subpictureClut(self.clut))

        # Reset the highlight state.
        self.area = None
        self.button = None
        self.palette = None

        self.segmentStart = None
        self.segmentStop = None

        self.flushing = True

        msg = gst.message_new_application(self.src,
                                          gst.Structure('seamless.Flush'))
        self.pipeline.get_bus().post(msg)

        self.vobuReadReturn = True

    def pause(self):
        """Pause the pipeline for a short time (currently 0.1s).

        Warning: This method temporarily releases the object's lock"""
        gst.debug("pause")

        # We don't want to keep the lock while sleeping.
        self.lock.release()
        time.sleep(0.1)
        self.lock.acquire()


    #
    # Signals
    #

    @signal
    def aspectRatioChanged(self, newAspectRatio):
        pass
