import sys
import string
import copy
import time
import traceback
import threading

from dvdread import *
from perform import *
import disassemble

from gobject import GObject
from gst import *


def MPEGTimeToGSTTime(mpegTime):
    return (long(mpegTime) * MSECOND) / 90

def strToISO639(strCode):
    strCode = string.lower(strCode)
    return ord(strCode[0]) * 0x100 + ord(strCode[1])

def ISO639ToStr(iso639):
    return chr(iso639 >> 8) + chr(iso639 & 0xff)


class MachineException(Exception):
    pass


# Command types
COMMAND_PRE = 1
COMMAND_CELL = 2
COMMAND_POST = 3


# A command disassembler for debugging.
disasm = disassemble.CommandDisassembler()


class PlaybackLocation(object):
    """A self-contained representation of a location in a DVD.

    A PlaybackLocation contains all information necessary to locate a
    position in the DVD and to play back starting from that
    position."""
    
    __slots__ = ['machine',
                 'info',
                 'title',
                 'chapter',
                 'programChain',
                 'cell',
                 'sectorNr',
                 'lastSectorNr',
                 'commandType',
                 'commands',
                 'commandNr',
                 'nav',
                 'button',
                 'stillEnd',
                 'interactive',
                 'cellCurrentTime']

    def __init__(self, machine, info):
        self.machine = machine
        self.info = info

        self.title = None
        self.chapter = None

        self.programChain = None
        self.nav = None
        self.commandType = None

        self.sectorNr = None
        self.lastSectorNr = None

        # Button one is highlighted by default (???)
        self.button = 1

        # No still frame in progress.
        self.stillEnd = None

        # Interactive is true when performing an interactive
        # operation.
        self.interactive = False

        self.cellCurrentTime = 0

    def set(self, location):
        """Set this location to the given location."""

        if self.interactive:
            # Make the interactive operation take place instantly.
            self.machine.flushEvent()
            self.machine.flushSource()
            self.interactive = False

        # Copy all slots.
        for attrName in self.__slots__:
            setattr(self, attrName, getattr(location, attrName))

    def jumpToUnit(self, unit):
        if isinstance(unit, VideoTitle):
            self.title = unit
            self.chapter = unit.getChapter(1)
            self.jump(self.chapter.cell.programChain)
        elif isinstance(unit, Chapter):
            self.title = unit.title
            self.chapter = unit
            if unit.chapterNr == 1:
                self.jumpToUnit(unit.cell.programChain)
            else:
                self.jumpToUnit(unit.cell)
            return
        else:
            self.jump(unit)

    def jump(self, subdiv):
        """Set the playback position to the given subdivision.
        """

        if self.interactive:
            # Make the interactive operation take place instantly.
            self.machine.flushEvent()
            self.machine.flushSource()
            self.interactive = False

        if isinstance(subdiv, ProgramChain):
            self.programChain = subdiv
            self.cell = None
            self.cellCurrentTime = 0
            self.sectorNr = None
            self.lastSectorNr = None

            self.nav = None
            self.commandType = None
        elif isinstance(subdiv, Cell):
            self.programChain = subdiv.programChain
            self.cell = subdiv
            self.sectorNr = subdiv.firstSector
            self.lastSectorNr = None

            self.nav = None
            self.commandType = None
        else:
            raise TypeError, "Parameter 2 of 'jump' has wrong type"

        # Suspend a possible still frame.
        self.stillEnd = None

        # Update the machine.
        self.machine.updatePipeline()

    def setCellByNumber(self, cellNr):
        """Set the location to the start of the cell with the given number."""

        self.jump(self.programChain.getCell(cellNr))

    def advanceSector(self, relSector):
        """Advance the current sector to the given relative postion."""

        self.sectorNr = self.lastSectorNr + relSector
        self.lastSectorNr = None

        # If we are trying to advance sectors we are already out of
        # interactive operation.
        self.interactive = False

    def useSector(self):
        """Retrieve the current sector for playback.

        The sector value will be reset to None to guarantee that it
        won't be used again."""

        sectorNr = self.sectorNr
        self.lastSectorNr = sectorNr
        self.sectorNr = None
        return sectorNr

    def setCommand(self, commandType, commandNr=1):
        """Set the location to the command with the given type and number."""

        self.sectorNr = None
        self.lastSectorNr = None

        self.commandType = commandType

        if commandType == COMMAND_PRE:
            self.commands = self.programChain.preCommands
        elif commandType == COMMAND_CELL:
            self.commands = self.programChain.cellCommands
        elif commandType == COMMAND_POST:
            self.commands = self.programChain.postCommands
        else:
            assert False

        self.commandNr = commandNr

        # Suspend a possible still frame.
        self.stillEnd = None

    def setNav(self, nav):
        """Set the current navigation packet.

        The location uses the navigation packet to tell the location
        of the next VOBU."""

        self.nav = nav

        self.cellCurrentTime = nav.cellElapsedTime.seconds


    #
    # Time Based Navigation
    #
    
    def getCurrentTime(self):
        if self.programChain == None:
            raise PlayerException, \
                  'No program chain currently playing'

        return  self.cell.startSeconds + self.cellCurrentTime

    currentTime = property(getCurrentTime)

    def getCanTimeJump(self):
        return self.programChain != None and \
               self.programChain.hasTimeMap

    canTimeJump = property(getCanTimeJump)

    def timeJump(self, seconds):
        if self.programChain == None:
            raise PlayerException, \
                  'Cannot time jump when no program chain is set'

        sectorNr = self.programChain.getSectorFromTime(seconds)
        self.jump(self.programChain.getCellFromSector(sectorNr))
        self.sectorNr = sectorNr


    #
    # Automatic Location Progress
    #

    def advance(self):
        """Advance the location in one execution step."""

        if self.stillEnd != None:
            if self.stillEnd != 0 and time.time() >= self.stillEnd:
                # Still time is over.
                self.stillEnd = None

                # Progress to the next cell at this point, waiting for
                # the next iteration will restart the still frame.
                if self.cell.commandNr != 0:
                    self.setCommand(COMMAND_CELL, self.cell.commandNr)
                elif self.cell.cellNr + 1 <= self.programChain.cellCount:
                    self.setCellByNumber(self.cell.cellNr + 1)
                else:
                    self.setCommand(COMMAND_POST)
        elif self.programChain == None:
            # Go to the first play pgc.
            self.jump(self.info.videoManager.firstPlay)
        elif self.commandType != None:
            # We are executing commands.
            if 1 <= self.commandNr <= self.commands.count:
                # We have a command to execute. Advance the program
                # counter before executing, to allow for goto to do
                # its job.
                cmd = self.commands.get(self.commandNr)
                self.commandNr += 1
                self.machine.performCommand(cmd)
            else:
                # We just came out of the current command set.
                if self.commandType == COMMAND_PRE:
                    if self.programChain.cellCount > 0:
                        self.setCellByNumber(1)
                    else:
                        self.setCommand(COMMAND_POST)
                elif self.commandType == COMMAND_CELL:
                    if self.cell.cellNr + 1 <= self.programChain.cellCount:
                        self.setCellByNumber(self.cell.cellNr + 1)
                    else:
                        self.setCommand(COMMAND_POST)
                elif self.commandType == COMMAND_POST and \
                     self.programChain.nextProgramChain != None:
                    self.jump(self.programChain.nextProgramChain)
                else:
                    # If we get to this point, we came out of the post
                    # command set. There's no defined operation to do
                    # here.
                    raise MachineException, 'Came out of a post command set'
        else:
            if self.cell == None:
                # Run the pre commands first.
                self.setCommand(COMMAND_PRE)
            else:
                # Try to advance to the next sector.
                if self.nav.nextVOBU != 0x3fffffff:
                    self.advanceSector(self.nav.nextVOBU)
                else:
                    # We reached the end of the current cell.
                    if self.cell.stillTime > 0:
                        # We have a still.
                        self.machine.stillFrameEvent()
                        if self.cell.stillTime == 0xff:
                            # Infinite still time.
                            self.stillEnd = 0
                        else:
                            self.stillEnd = time.time() + \
                                            self.cell.stillTime
                    elif self.cell.commandNr != 0:
                        self.setCommand(COMMAND_CELL, self.cell.commandNr)
                    elif self.cell.cellNr + 1 <= self.programChain.cellCount:
                        self.setCellByNumber(self.cell.cellNr + 1)
                    else:
                        self.setCommand(COMMAND_POST)

    def getDomain(self):
        if isinstance(self.programChain.container, LangUnit):
            return DOMAIN_MENU
        else:
            return DOMAIN_TITLE

    def getAttributeContainer(self):
        """Find the container of the current stream attributes."""

        if isinstance(self.programChain.container, LangUnit):
            return self.programChain.container.container
        elif isinstance(self.programChain.container, VideoTitleSet):
            return self.programChain.container
        elif isinstance(self.programChain.container, VideoManager):
            return self.programChain.container
        else:
            assert 0, 'Unexpected type for program chain container'

    def nextVOBU(self):
        if self.stillEnd != None:
            self.advance()

        while self.stillEnd == None and self.sectorNr == None:
            self.advance()

        # Find the current playback title number.
        if isinstance(self.programChain.container, LangUnit):
            titleNr = self.programChain.container.container.titleSetNr
        elif isinstance(self.programChain.container, VideoTitleSet):
            titleNr = self.programChain.container.titleSetNr
        elif isinstance(self.programChain.container, VideoManager):
            titleNr = 0
        else:
            assert 0, 'Unexpected type for program chain container'

        return (self.getDomain(), titleNr, self.useSector())


class VirtualMachine(CommandPerformer):
    """A DVD playback virtual machine implementation."""

    __slots__ = ['info',
                 'src',
                 'lock',
                 'pendingEvents',
                 'audio',
                 'subpicture',
                 'angle',
                 'audioPhys',
                 'subpicturePhys',
                 'buttonNav',
                 'highlightArea',
                 'highlightProgramChain',
                 'regionCode',
                 'prefMenuLang',
                 'prefAudio',
                 'prefSubpicture',
                 'parentalCountry',
                 'parentalLevel',
                 'aspectRatio',
                 'videoMode',
                 'generalRegisters',
                 'location',
                 'resumelocation']

    def __init__(self, info, src):
        self.info = info
        self.src = src

        # The synchronized method lock.
        self.lock = threading.RLock()

        # The queue of pending events.
        self.pendingEvents = []

        src.connect('vobu-read', self.vobuRead)
        src.connect('vobu-header', self.vobuHeader)

        # Current logical audio and subpicture streams and current
        # angle. The values follow the conventions of system registers
        # 1, 2, and 3, respectively.
        self.audio = 0		# This seems to be needed by some DVDs.
        self.subpicture = 0x3e	# None
        self.angle = 1

        # Pipeline state.
        self.audioPhys = -1
        self.subpicturePhys = -1
        self.buttonNav = None
        self.highlightArea = None
        self.highlightProgramChain = None


        # Machine options and state:

        # Region Code
        self.regionCode = 0  # Region free.

        # Preferred languages.
        self.prefMenuLang = 'en'
        self.prefAudio = None
        self.prefSubpicture = None

        # Parental level country and level value.
        self.parentalCountry = 'us'
        self.parentalLevel = 15 # None

        # Prefered display aspect ratio
        self.aspectRatio = ASPECT_RATIO_16_9

        # Current video mode.
        self.videoMode = VIDEO_MODE_NORMAL


        # Initialize all machine registers.
        self.initializeRegisters()

        # Location and resume location.
        self.location = PlaybackLocation(self, info)
        self.resumelocation = None

        # Start running the first play program chain.
        self.location.jumpToUnit(self.info.videoManager.firstPlay)


    #
    # Method Synchronization
    #

    def synchronized(method):
        def wrapper(self, *args, **keywords):
            self.lock.acquire()
            try:
                method(self, *args, **keywords)
            finally:
                self.lock.release()

        return wrapper


    #
    # Signal Handling
    #

    def vobuRead(self, src):
        
        self.lock.acquire()
        
        try:
            (domain, titleNr, sectorNr) = self.location.nextVOBU()
        except:
            traceback.print_exc()
            sys.exit(1)

        if sectorNr != None:
            self.src.set_property('domain', domain)
            self.src.set_property('title', titleNr)
            src.set_property('vobu-start', sectorNr)
        else:
            # We are displaying a still frame, send a filler event
            # to keep the pipeline busy.
            self.fillerEvent()

        # Send all queued events.
        while len(self.pendingEvents) > 0:
            self.src.get_pad('src').push(self.pendingEvents.pop(0))

        #print >> sys.stderr, 'Current VOBU:', self.location.lastSectorNr,
        #print >> sys.stderr, '\r',

        self.lock.release()
        
        # Be nice to the processor, but don't sleep while blocked.
        if sectorNr == None:
            time.sleep(0.1)

    def vobuHeader(self, src, buffer):
        nav = NavPacket(buffer.get_data())

        self.location.setNav(nav)

        # FIXME: The current buttonNav should be based on the current
        # value of the clock.
        self.setButtonNav(nav)

        # Send a nav-packet event
        st = Structure('application/x-gst-dvd')
        st.set_value('event', 'dvd-nav-packet')
        st.set_value('start_ptm', MPEGTimeToGSTTime(nav.startTime))
        st.set_value('end_ptm', MPEGTimeToGSTTime(nav.endTime))
        self.src.get_pad('src').push(event_new_any(st))

    vobuHeader = synchronized(vobuHeader)

    def flushSource(self):
        """Stop the source on its tracks."""

        self.src.set_property('block-count', 0)


    #
    # Events
    #

    def queueEvent(self, event):
        self.pendingEvents.append(event)

    def flushEvent(self):
        self.pendingEvents = []
        self.queueEvent(Event(EVENT_FLUSH))

        # A flush cleans up the displayed highlight.
        self.highlightArea = None

    def fillerEvent(self):
        self.queueEvent(Event(EVENT_FILLER))

    def stillFrameEvent(self):
        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-still-frame')
        self.queueEvent(event_new_any(st))

    def audioEvent(self):
        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-audio-stream-change')
        st.set_value('physical', self.audioPhys)
        self.queueEvent(event_new_any(st))
        #print >> sys.stderr, 'New audio:', self.audioPhys

    def subpictureEvent(self):
        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-stream-change')
        st.set_value('physical', self.subpicturePhys)
        self.queueEvent(event_new_any(st))
        #print >> sys.stderr, 'New subpicture:', self.subpicturePhys

    def subpictureCLUTEvent(self):
        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-clut-change')

        # Each value is stored in a separate field.
        for i in range(16):

            st.set_value('clut%02d' % i,
                         self.highlightProgramChain.getCLUTEntry(i + 1))

        self.queueEvent(event_new_any(st))

    def highlightEvent(self):
        if self.highlightArea != None:
            btnObj = self.buttonNav.getButton(self.location.button)
            (sx, sy, ex, ey) = btnObj.area

            st = Structure('application/x-gst-dvd');
            st.set_value('event', 'dvd-spu-highlight')
            st.set_value('button', self.location.button)
            st.set_value('palette', btnObj.paletteSelected)
            st.set_value('sx', sx)
            st.set_value('sy', sy)
            st.set_value('ex', ex)
            st.set_value('ey', ey)
        else:
            st = Structure('application/x-gst-dvd')
            st.set_value('event', 'dvd-spu-reset-highlight')

        # Send the event inmediatly for better interactive response,
        # but put a delayed version in the queue for situations where
        # a flush is involved.
        self.src.get_pad('src').push(event_new_any(st))
        self.queueEvent(event_new_any(st))

    def updatePipeline(self):
        # Update the audio, if necessary.
        if self.location.getDomain() == DOMAIN_TITLE:
            if self.audio == 15 or \
               self.location.programChain == None:
                physical = -1
            else:
                physical = self.location.programChain. \
                           getAudioPhysStream(self.audio + 1)
                if physical == None:
                    # Just pick the first existing stream.
                    physical = -1
                    for logical in range(1, 9):
                        newPhys = self.location.programChain. \
                                  getAudioPhysStream(logical)
                        if newPhys != None:
                            physical = newPhys
                            break
        else:
            physical = 0

        if self.audioPhys != physical:
            self.audioPhys = physical
            self.audioEvent()

        # Update the subpicture, if necessary.
        if self.location.getDomain() == DOMAIN_TITLE:
            if self.location.programChain == None or \
               self.subpicture & 0x40 == 0 or \
               self.subpicture & 0x3f > 31:
                physical = -1
            else:
                streams = self.location.programChain. \
                          getSubpicturePhysStreams((self.subpicture \
                                                    & 0x1f) + 1)
                if streams == None:
                    physical = -1
                else:
                    if self.location.getAttributeContainer(). \
                       videoAttributes.aspectRatio == ASPECT_RATIO_4_3:
                        physical = streams[SUBPICTURE_PHYS_TYPE_4_3]
                    else:
                        if self.aspectRatio == ASPECT_RATIO_16_9:
                            physical = streams[SUBPICTURE_PHYS_TYPE_WIDESCREEN]
                        else:
                            physical = streams[SUBPICTURE_PHYS_TYPE_LETTERBOX]
        else:
            physical = 0

        if self.subpicturePhys != physical:
            self.subpicturePhys = physical
            self.subpictureEvent()

        # Update the subpicture color lookup table, if necessary.
        if self.location.programChain != None and \
           self.location.programChain != self.highlightProgramChain:
            self.highlightProgramChain = self.location.programChain
            self.subpictureCLUTEvent()

        # Update the highlight area, if necessary.
        if self.buttonNav == None or \
           self.buttonNav.highlightStatus == HLSTATUS_NONE or \
           not 1 <= self.location.button <= self.buttonNav.buttonCount:
            area = None
        else:
            area = self.buttonNav.getButton(self.location.button).area

        if self.highlightArea != area:
            self.highlightArea = area
            self.highlightEvent()


    #
    # Language Units
    #

    def getLangUnit(self, container):
        unit = container.getLangUnit(self.prefMenuLang)
        if unit == None:
            unit = container.getLangUnit(1)

        return unit


    #
    # Registers
    #

    class Register(object):
        pass

    class GeneralRegister(Register):
        def __init__(self):
            self.value = 0

        def getValue(self):
            return self.value

        def setValue(self, value):
            assert isinstance(value, int)
            
            self.value = value & 0xffff


    class SystemRegister(Register):
        def __init__(self, method):
            self.method = method

        def getValue(self):
            return self.method()

        def setValue(self, value):
             raise MachineException, \
                   'Attempt to directly assign a system register'


    def getSystem0(self):
        """Return the value of system register 0 (menu_language)."""
        return strToISO639(self.prefMenuLang)

    def getSystem1(self):
        """Return the value of system register 1 (audio_stream)."""
        return self.audio

    def getSystem2(self):
        """Return the value of system register 2 (subpicture_stream)."""
        return self.subpicture

    def getSystem3(self):
        """Return the value of system register 3 (angle)."""
        return self.angle

    def getSystem4(self):
        """Return the value of system register 4 (title_in_volume)."""
        if self.location.title != None:
            return self.location.title.globalTitleNr
        else:
            return 1

    def getSystem5(self):
        """Return the value of system register 5 (title_in_vts)."""
        if self.location.title != None:
            return self.location.title.titleNr
        else:
            return 1

    def getSystem6(self):
        """Return the value of system register 6 (program_chain)."""
        if self.location.programChain != None:
            return self.location.programChain.programChainNr
        else:
            return 0

    def getSystem7(self):
        """Return the value of system register 7 (chapter)."""
        if self.location.chapter != None:
            return self.location.chapter.chapterNr
        else:
            return 1

    def getSystem8(self):
        """Return the value of system register 8 (highlighted_button)."""
        return self.location.button << 10

    def getSystem9(self):
        """Return the value of system register 9 (navigation_timer)."""
        print >> sys.stderr, "Navigation timer checked, implement me!"
        return 0

    def getSystem10(self):
        """Return the value of system register 10 (program_chain_for_timer)."""
        print >> sys.stderr, "Navigation timer checked, implement me!"
        return 0

    def getSystem11(self):
        """Return the value of system register 11 (karaoke_mode)."""
        print >> sys.stderr, "Karaoke mode checked, implement me!"
        return 0

    def getSystem12(self):
        """Return the value of system register 12 (parental_country)."""
        return strToISO639(self.parentalCountry)

    def getSystem13(self):
        """Return the value of system register 13 (parental_level)."""
        return self.parentalLevel

    def getSystem14(self):
        """Return the value of system register 14 (video_mode_pref)."""
        return self.aspectRatio << 10 | self.videoMode << 8

    def getSystem15(self):
        """Return the value of system register 15 (audio_caps)."""
        return 0x4000

    def getSystem16(self):
        """Return the value of system register 16 (audio_lang_pref)."""
        if self.prefAudio != None:
            return self.prefAudio
        else:
            return 0xffff  # Not specified

    def getSystem17(self):
        """Return the value of system register 17 (audio_ext_pref)."""
        return 0

    def getSystem18(self):
        """Return the value of system register 18 (subpicture_lang_pref)."""
        if self.prefSubpicture != None:
            return self.prefSubpicture
        else:
            return 0xffff  # Not specified

    def getSystem19(self):
        """Return the value of system register 19 (subpicture_ext_pref)."""
        return 0

    def getSystem20(self):
        """Return the value of system register 20 (region_code)."""
        return self.regionCode

    def getSystem21(self):
        """Return the value of system register 21 (reserved)."""
        return 0

    def getSystem22(self):
        """Return the value of system register 22 (reserved)."""
        return 0

    def getSystem23(self):
        """Return the value of system register 23 (reserved_ext_playback)."""
        return 0


    def initializeRegisters(self):
        self.generalRegisters = []
        for i in range(16):
            self.generalRegisters.append(self.GeneralRegister())

        self.systemRegisters = []
        for i in range(24):
            self.systemRegisters.append( \
                self.SystemRegister(getattr(self, "getSystem%d" % i)))

    def getGeneralPurpose(self, regNr):
        assert 0 <= regNr <= 15
        return self.generalRegisters[regNr]

    def getSystemParameter(self, regNr):
        assert 0 <= regNr <= 23
        return self.systemRegisters[regNr]


    #
    # Command Execution
    #

    def nop(self):
        pass

    def goto(self, commandNr):
        self.location.commandNr = commandNr

    def brk(self):
        # 'Go to' an inexistent command. The location will do the rest.
        self.location.commandNr = self.location.commands.count + 1

    def exit(self):
        # FIXME
        print >> sys.stderr, "Machine exited"

    def openSetParentalLevel(self, cmd):
        print >> sys.stderr, "Set parental level tried, implement me!"
        return TRUE

    def linkTopCell(self):
        self.location.jumpToUnit(self.location.cell)

    def linkNextCell(self):
        self.location.jumpToUnit(self.location.programChain. \
                                 getCell(self.location.cell.cellNr + 1))

    def linkPrevCell(self):
        self.location.jumpToUnit(self.location.programChain. \
                                 getCell(self.location.cell.cellNr - 1))

    def linkTopProgram(self):
        programNr = self.location.cell.programNr
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr))

    def linkNextProgram(self):
        programNr = self.location.cell.programNr
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr + 1))

    def linkPrevProgram(self):
        programNr = self.location.cell.programNr
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr - 1))

    def linkTopProgramChain(self):
        self.location.jumpToUnit(self.location.programChain)

    def linkNextProgramChain(self):
        self.location.jumpToUnit(self.location.programChain.nextProgramChain)

    def linkPrevProgramChain(self):
        self.location.jumpToUnit(self.location.programChain.prevProgramChain)

    def linkGoUpProgramChain(self):
        self.location.jumpToUnit(self.location.programChain.goUpProgramChain)

    def linkTailProgramChain(self):
        self.location.setCommand(COMMAND_POST)

    def linkProgramChain(self, programChainNr):
        self.location.jumpToUnit(self.location.programChain.container. \
                                 getProgramChain(programChainNr))

    def linkChapter(self, chapterNr):
        self.location.jumpToUnit(self.location.title.getChapter(chapterNr))

    def linkProgram(self, programNr):
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr))

    def linkCell(self, cellNr):
        self.location.jumpToUnit(self.location.programChain.getCell(cellNr))

    def selectButton(self, buttonNr):
        if not 0 <= buttonNr <= 36:
            raise MachineException, "Button number out of range"

        self.location.button = buttonNr
        self.updatePipeline()

    def setSystemParam8(self, value):
        self.selectButton(value >> 10)

    def jumpToTitle(self, titleNr):
        self.location.jumpToUnit(self.info.videoManager.getVideoTitle(titleNr))

    def jumpToTitleInSet(self, titleNr):
        self.location.jumpToUnit(self.location.title.videoTitleSet. \
                                 getVideoTitle(titleNr))

    def jumpToChapterInSet(self, titleNr, chapterNr):
        self.location.jumpToUnit(self.location.title.videoTitleSet. \
                                 getVideoTitle(titleNr).getChapter(chapterNr))

    def jumpToFirstPlay(self):
        self.location.jumpToUnit(self.info.videoManager.firstPlay)

    def jumpToTitleMenu(self):
        langUnit = self.getLangUnit(self.info.videoManager)
        self.location.jumpToUnit(langUnit.getMenuProgramChain(MENU_TYPE_TITLE))

    def jumpToMenu(self, titleSetNr, titleNr, menuType):
        # Get the title set. Title set 0 is the video manager.
        if titleSetNr == 0:
            titleSet = self.info.videoManager
        else:
            titleSet = self.info.videoManager.getVideoTitleSet(titleSetNr)

        # Jump first to the video title to make sure that the location
        # points to the right title.
        title = titleSet.getVideoTitle(titleNr)
        self.location.jumpToUnit(title)
        
        # Now jump to the actual program chain corresponding to the menu..
        langUnit = self.getLangUnit(title.videoTitleSet)
        self.location.jumpToUnit(langUnit.getMenuProgramChain(menuType))

    def jumpToManagerProgramChain(self, programChainNr):
        langUnit = self.getLangUnit(self.info.videoManager)
        self.location.jumpToUnit(langUnit.getProgramChain(programChainNr))

    def setTimedJump(self, programChainNr, seconds):
        print >> sys.stderr, "Timed jump, implement me!"

    def saveLocation(self, rtn=0):
        """Save the current location in the resume location.

        If rtn is not zero, it specifies the cell number to return to
        when the saved state is resumed."""

        if rtn != 0:
            self.linkCell(rtn)
        self.resumeLocation = copy.copy(self.location)

    def callFirstPlay(self, rtn=0):
        self.saveLocation(rtn)
        self.jumpToFirstPlay()

    def callTitleMenu(self, rtn=0):
        self.saveLocation(rtn)
        self.jumpToTitleMenu()

    def callMenu(self, menuType, rtn=0):
        self.saveLocation(rtn)
        titleSetNr = self.location.title.videoTitleSet.titleSetNr
        titleNr = self.location.title.titleNr
        self.jumpToMenu(titleSetNr, titleNr, menuType)

    def callManagerProgramChain(self, programChainNr, rtn=0):
        self.saveLocation(rtn)
        self.jumpToManagerProgramChain(programChainNr)

    def resume(self):
        if self.resumeLocation == None:
            raise PlayerException, "Attempt to resume with no resume info"

        # We set the current location to allow for it to continue
        # playback from the resume point.
        self.location.set(self.resumeLocation)
        self.resumeLocation = None

        self.updatePipeline()

    def setAngle(self, angle):
        if self.angle != angle:
            self.angle = angle

    def setAudio(self, audio):
        if self.audio != audio:
            self.audio = audio

    def setSubpicture(self, subpicture):
        if self.subpicture != subpicture:
            self.subpicture = subpicture

    def setKaraokeMode(self, mode):
        print >> sys.stderr, "Attemp to set karaoke mode, implement me!"


    def performCommand(self, cmd):
        global disasm

        disasm.decodeCommand(cmd, self.location.commandNr - 1)
        print >> sys.stderr, disasm.getText()
        disasm.resetText()

        try:
            CommandPerformer.performCommand(self, cmd)
        except:
            print >> sys.stderr, "Error while executing command:"
            print >> sys.stderr, "----- Traceback -----"
            traceback.print_exc()
            print >> sys.stderr, "----- End traceback -----"

    def performCommandInteractive(self, cmd):
        self.location.interactive = True
        self.performCommand(cmd)


    #
    # Playback Control
    #

    def jump(self, subdiv):
        self.flushEvent()
        self.location.jumpToUnit(subdiv)
        self.flushSource()

    jump = synchronized(jump)

    def stop(self):
        self.flushEvent()
        self.flushSource()

    stop = synchronized(stop)

    def prevProgram(self):
        programNr = self.location.cell.programNr - 1
        if programNr < 1:
            # If we are playing program 1, go to the beginning.
            programNr = 1
        self.jump(self.location.programChain.getProgramCell(programNr))

    prevProgram = synchronized(prevProgram)

    def nextProgram(self):
        programNr = self.location.cell.programNr + 1
        if programNr <= self.location.programChain.programCount:
            self.jump(self.location.programChain.getProgramCell(programNr))

    nextProgram = synchronized(nextProgram)


    #
    # Time Based Navigation
    #

    def getCurrentTime(self):
        return self.location.getCurrentTime()
    currentTime = property(getCurrentTime)

    def getCanTimeJump(self):
        return self.location.getCanTimeJump()
    canTimeJump = property(getCanTimeJump)

    def timeJump(self, seconds):
        self.flushEvent()
        self.location.timeJump(seconds)
        self.flushSource()

    timeJump = synchronized(timeJump)

    def timeJumpRelative(self, seconds):
        self.timeJump(self.location.currentTime + seconds)

    timeJumpRelative = synchronized(timeJumpRelative)


    #
    # Stream Control
    #

    def getAudioStream(self):
        return self.audio + 1

    def setAudioStream(self, logical):
        if not 1 <= logical <= 8:
            raise MachineException, "Invalid logical stream number"

        self.audio = logical - 1
        self.updatePipeline()

    audioStream = property(getAudioStream, setAudioStream)

    def getAudioStreams(self):
        if self.location.programChain == None:
            return []

        streams = []
        for logical in range(1, 9):
            if self.location.programChain.getAudioPhysStream(logical) \
               != None:
                streams.append((logical,
                                self.location.title.videoTitleSet. \
                                getAudioAttributes(logical)))

        return streams


    #
    # Button Navigation
    #

    def setButtonNav(self, buttonNav):
        # Check for forced select.
        if 1 <= buttonNav.forcedSelect <= 36 and \
           (self.buttonNav == None or \
            self.buttonNav.forcedSelect != buttonNav.forcedSelect):
            self.selectButton(buttonNav.forcedSelect)

        self.buttonNav = buttonNav

        # Check for forced activate.
        if 1 <= buttonNav.forcedActivate <= 36:
            self.selectButton(buttonNav.forcedActivate)
            self.confirm()

        if (buttonNav.highlightStatus == HLSTATUS_NONE and \
            self.highlightArea != None) or \
            buttonNav.highlightStatus == HLSTATUS_NEW_INFO:
            self.updatePipeline()

    def getButtonObj(self):
        if self.buttonNav == None or \
           self.buttonNav.highlightStatus == HLSTATUS_NONE or \
           not 1 <= self.location.button <= self.buttonNav.buttonCount:
            return None
        else:
            return self.buttonNav.getButton(self.location.button)

    def selectButtonInteractive(self, buttonNr):
        self.selectButton(buttonNr)

        btnObj = self.getButtonObj()
        if btnObj != None and btnObj.autoAction:
            self.confirm()

    def up(self):
        btnObj = self.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.up
        if nextBtn != 0:
            self.selectButtonInteractive(nextBtn)

    up = synchronized(up)

    def down(self):
        btnObj = self.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.down
        if nextBtn != 0:
            self.selectButtonInteractive(nextBtn)

    down = synchronized(down)

    def left(self):
        btnObj = self.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.left
        if nextBtn != 0:
            self.selectButtonInteractive(nextBtn)

    left = synchronized(left)

    def right(self):
        btnObj = self.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.right
        if nextBtn != 0:
            self.selectButtonInteractive(nextBtn)

    right = synchronized(right)

    def confirm(self):
        btnObj = self.getButtonObj()
        if btnObj == None:
            return

        self.location.setCommand(COMMAND_CELL)
        self.performCommandInteractive(btnObj.command)

    confirm = synchronized(confirm)

    def menu(self):
        if self.location.getDomain() != DOMAIN_TITLE:
            return

        self.flushEvent()
        self.flushSource()

        self.callMenu(MENU_TYPE_ROOT)

    menu = synchronized(menu)

    def rtn(self):
        if self.location.getDomain() != DOMAIN_MENU:
            return

        self.flushEvent()
        self.flushSource()

        self.resume()

    rtn = synchronized(rtn)
