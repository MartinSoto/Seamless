#!/usr/bin/env python2.3

import sys
import string

from dvdread import *


def MPEGTimeToGSTTime(mpegTime):
    return (long(mpegTime) * gst.MSECOND) / 90


class PlayerException(Exception):
    pass


class BasicPlayer(object):
    """
    """

    def __init__(self, src):
        self.src = src

        # Current playback position
        self.currentProgramChain = None
        self.currentCell = None
        self.currentVOBU = -1

        # Current logical audio and subpicture streams. None as value
        # means no stream selected.
        self.currentAudio = None
        self.currentSubpicture = None

        # Last seen nav packet.
        self.nav = None

        # The queue of pending events
        self.pendingEvents = []

        # True when there is a pending flush/discont event pair to be
        # sent.
        self.pendingDiscont = False

        src.connect('vobu-read', self.vobuRead)
        src.connect('vobu-header', self.vobuHeader)

    #
    # Event Handling
    #

    def queueEvent(self, event):
        self.pendingEvents.append(event)

    def flushEvent(self):
        self.queueEvent(Event(EVENT_FLUSH))

    def navPacketEvent(self, startTime, endTime):
        st = Structure('application/x-gst-dvd')
        st.set_value('event', 'dvd-nav-packet')
        st.set_value('start_ptm', MPEGTimeToGSTTime(startTime))
        st.set_value('end_ptm', MPEGTimeToGSTTime(endTime))
        self.queueEvent(event_new_any(st))

    def audioEvent(self):
        if self.currentProgramChain == None:
            return

        if self.currentAudio == None:
            # FIXME: Send some sort of reset event here.
            return

        physical = self.currentProgramChain. \
                   getAudioPhysStream(self.currentAudio)
        if physical == None:
            return

        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-audio-stream-change')
        st.set_value('physical', physical)
        if self.currentSubpicture != None:
            st.set_value('logical', self.currentAudio)
        self.queueEvent(event_new_any(st))

    def subpictureEvent(self):
        if self.currentProgramChain == None:
            return

        if self.currentSubpicture == None:
            physical = -1
        else:
            streams = self.currentProgramChain. \
                      getSubpicturePhysStreams(self.currentSubpicture)
            if streams == None:
                physical = -1
            else:
                # FIXME: This should work with all video modes.
                physical = streams['widescreen']

        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-stream-change')
        st.set_value('physical', physical)
        if self.currentSubpicture != None:
            st.set_value('logical', self.currentSubpicture)
        self.queueEvent(event_new_any(st))

    def subpictureCLUTEvent(self):
        if self.currentProgramChain == None:
            returnq

        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-clut-change')

        # Each value is stored in a separate field.
        for i in range(16):
            st.set_value('clut%02d' % i,
                         self.currentProgramChain.getCLUTEntry(i + 1))

        self.queueEvent(event_new_any(st))

    #
    # Playback Control
    #

    def jump(self, obj):
        """Jump to the DVD subdivision pointed to by obj."""

        if isinstance(obj, VideoTitle):
            self.jump(obj.getChapter(1))
            return
        elif isinstance(obj, Chapter):
            self.jump(obj.cell)
            return
        elif isinstance(obj, ProgramChain):
            self.jump(obj.getCell(1))
            return
        elif isinstance(obj, Cell):
            self.currentProgramChain = obj.programChain
            self.currentCell = obj
            self.currentVOBU = self.currentCell.firstSector
            self.performJump()
        else:
            raise TypeError, 'Parameter 2 of jump has wrong type'

    def getTotalTime(self):
        if self.currentProgramChain == None:
            raise PlayerException, \
                  'No program chain currently playing'

        return self.currentProgramChain.playbackTime.seconds
    
    totalTime = property(getTotalTime)

    def getCurrentTime(self):
        if self.currentProgramChain == None:
            raise PlayerException, \
                  'No program chain currently playing'

        return self.currentCell.startSeconds + \
               self.nav.cellElapsedTime.seconds

    currentTime = property(getCurrentTime)

    def getCanTimeJump(self):
        return self.currentProgramChain != None and \
               self.currentProgramChain.hasTimeMap
    
    canTimeJump = property(getCanTimeJump)

    def timeJump(self, seconds):
        if self.currentProgramChain == None:
            raise PlayerException, \
                  'Cannot time jump when no program chain is set'

        self.currentVOBU = self.currentProgramChain. \
                           getSectorFromTime(seconds)
        self.currentCell = self.currentProgramChain. \
                           getCellFromSector(self.currentVOBU)
        self.performJump()

    def timeJumpRelative(self, seconds):
        self.timeJump(self.currentTime + seconds)

    def performJump(self):
        # Set the playback properties in the source element.
        if isinstance(self.currentProgramChain.container, LangUnit):
            titleNr = self.currentProgramChain.container.container.titleSetNr
            domain = DOMAIN_MENU
        elif isinstance(self.currentProgramChain.container, VideoTitleSet):
            titleNr = self.currentProgramChain.container.titleSetNr
            domain = DOMAIN_TITLE
        elif isinstance(self.currentProgramChain.container, VideoManager):
            titleNr = 0
            domain = DOMAIN_TITLE
        else:
            raise TypeError, 'Unexpected type for program chain container'

        self.src.set_property('domain', domain)
        self.src.set_property('title', titleNr)
        self.src.set_property('vobu-start', self.currentVOBU)

        # Set the physical audio and subpicture streams.
        self.audioEvent()
        self.subpictureCLUTEvent()
        self.subpictureEvent()

        # Prepare to signal a discontinuity.
        self.pendingDiscont = True

    def prevProgram(self):
        programNr = self.currentCell.programNr - 1
        if programNr < 1:
            programNr = 1
        self.jump(self.currentProgramChain.getProgramCell(programNr))

    def nextProgram(self):
        programNr = self.currentCell.programNr + 1
        if programNr <= self.currentProgramChain.programCount:
            self.jump(self.currentProgramChain.getProgramCell(programNr))

    def setAudio(self, logical):
        if not (logical == None or \
                (isinstance(logical, int) and 1 <= logical <= 8)):
            raise PlayerException, "invalid logical audio stream number"

        if self.currentAudio != logical:
            self.currentAudio = logical
            self.audioEvent()

    def getAudio(self):
        return self.currentAudio

    audio = property(getAudio, setAudio)

    def setSubpicture(self, logical):
        if not (logical == None or \
                (isinstance(logical, int) and 1 <= logical <= 32)):
            raise PlayerException, \
                  "invalid logical subpicture stream number"

        if self.currentSubpicture != logical:
            self.currentSubpicture = logical
            self.subpictureEvent()

    def getSubpicture(self):
        return self.currentSubpicture

    subpicture = property(getSubpicture, setSubpicture)


    #
    # Signal Handling
    #

    def vobuRead(self, src):
        if self.currentVOBU == -1:
            return

        src.set_property('vobu-start', self.currentVOBU)

    def vobuHeader(self, src, buffer):
        self.nav = NavPacket(buffer.get_data())

        if self.pendingDiscont:
            self.flushEvent()
            self.pendingDiscont = False

        # Queue a nav-packet event
        self.navPacketEvent(self.nav.startTime, self.nav.endTime)

        if self.nav.nextVOBU == 0x3fffffff:
            # We reached the end of the current cell.
            if self.currentCell.cellNr < self.currentProgramChain.cellCount:
                self.currentCell = self.currentProgramChain. \
                                   getCell(self.currentCell.cellNr + 1)
                self.currentVOBU = self.currentCell.firstSector
            else:
                print >> sys.stderr, '*** Jumping PGC'
                # We reached the end of the program chain.
                self.currentProgramChain = self.currentProgramChain. \
                                           nextProgramChain
                if self.currentProgramChain != None:
                    self.currentCell = self.currentProgramChain.getCell(1)
                    self.currentVOBU = self.currentCell.firstSector
                else:
                    self.currentProgramChain = None
                    self.currentCell = None
                    self.currentVOBU = -1
        else:
            self.currentVOBU += self.nav.nextVOBU

        # Send all queued events.
        while len(self.pendingEvents) > 0:
            self.src.get_pad('src').push(self.pendingEvents.pop(0))

        #print >> sys.stderr, 'Current VOBU: %ld\r' % self.currentVOBU,
        #print >> sys.stderr, 'Time: %s\r' % str(self.nav.cellElapsedTime),


