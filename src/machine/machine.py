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

"""Main implementation of DVD virtual machine."""

import sys
import traceback
import threading

from itersched import *

import dvdread
import decode
import disassemble

import gst


def mpegTimeToGstTime(mpegTime):
    """Convert MPEG time values to the GStreamer time format."""
    return (long(mpegTime) * dvdread.MSECOND) / 90

def strToIso639(strCode):
    """Encode an ISO639 country name to byte form."""
    strCode = strCode.lower()
    return ord(strCode[0]) * 0x100 + ord(strCode[1])

def iso639ToStr(iso639):
    """Decode an ISO639 country names from byte form."""
    return chr(iso639 >> 8) + chr(iso639 & 0xff)


class MachineException(Exception):
    """Base class for exceptions caused by the virtual machine."""
    pass


# A command disassembler for debugging.
disasm = disassemble.CommandDisassembler()


def synchronized(method):
    """Wrapper for syncronized methods."""

    def wrapper(self, *args, **keywords):
        self.lock.acquire()
        try:
            method(self, *args, **keywords)
        finally:
            self.lock.release()

    return wrapper


class EosEvent(object):
    """A token representing an EOS event in the event queue."""
    pass


class Register(decode.Register):
    __slots__ = ()


class GeneralRegister(Register):
    __slots__ = ('value',)

    def __init__(self):
        self.value = 0

    def getValue(self):
        return self.value

    def setValue(self, value):
        assert isinstance(value, int)

        self.value = value & 0xffff


class SystemRegister(Register):
    __slots__ = ('method',)

    def __init__(self, method):
        self.method = method

    def getValue(self):
        return self.method()

    def setValue(self, value):
        raise MachineException, \
              'Attempt to directly assign a system register'


def makeMachineOperation(method):
    def restartOp(self, *args):
        yield getattr(Restart, method)(*args)

    return restartOp


class PlaybackLocation(object):
    """A self-contained representation of a location in a DVD.

    A PlaybackLocation contains all information necessary to locate a
    position in the DVD and to play back starting from that
    position."""
    
    __slots__ = ('title',
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
                 'cellCurrentTime')

    def __init__(self):
        self.title = None
        self.chapter = None

        self.programChain = None
        self.nav = None
        self.commandType = None

        self.sectorNr = None
        self.lastSectorNr = None

        # Button one is highlighted by default (???)
        self.button = 1

        self.cellCurrentTime = 0


class PerformMachine(object):
    __slots__ = ('audio',
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

                 'location',
                 'resumeLocation',

                 'generalRegisters',
                 'systemRegisters')

    def __init__(self):
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

        # Preferred display aspect ratio
        self.aspectRatio = dvdread.ASPECT_RATIO_16_9

        # Current video mode.
        self.videoMode = dvdread.VIDEO_MODE_NORMAL

        # Location and resume location.
        self.location = PlaybackLocation()
        self.resumeLocation = None

        # Initialize all machine registers.
        self.generalRegisters = None
        self.systemRegisters = None
        self.initializeRegisters()


    #
    # Machine Operations
    #

    # Basic operations.
    nop = makeMachineOperation('nop')
    goto = makeMachineOperation('goto')
    brk = makeMachineOperation('break')
    exit = makeMachineOperation('exit')

    # Parental management
    openSetParentalLevel = makeMachineOperation('openSetParentalLevel')

    # Links.
    linkTopCell = makeMachineOperation('linkTopCell')
    linkNextCell = makeMachineOperation('linkNextCell')
    linkPrevCell = makeMachineOperation('linkPrevCell')
    linkTopProgram = makeMachineOperation('linkTopProgram')
    linkNextProgram = makeMachineOperation('linkNextProgram')
    linkPrevProgram = makeMachineOperation('linkPrevProgram')
    linkTopProgramChain = makeMachineOperation('linkTopProgramChain')
    linkNextProgramChain = makeMachineOperation('linkNextProgramChain')
    linkPrevProgramChain = makeMachineOperation('linkPrevProgramChain')
    linkGoUpProgramChain = makeMachineOperation('linkGoUpProgramChain')
    linkTailProgramChain = makeMachineOperation('linkTailProgramChain')
    linkProgramChain = makeMachineOperation('linkProgramChain')
    linkChapter = makeMachineOperation('linkChapter')
    linkProgram = makeMachineOperation('linkProgram')
    linkCell = makeMachineOperation('linkCell')

    # Select (highlight) a button
    selectButton = makeMachineOperation('selectButton')
    setSystemParam8 = makeMachineOperation('selectButton')

    # Jumps
    jumpToTitle = makeMachineOperation('jumpToTitle')
    jumpToTitleInSet = makeMachineOperation('jumpToTitleInSet')
    jumpToChapterInSet = makeMachineOperation('jumpToChapterInSet')

    jumpToFirstPlay = makeMachineOperation('jumpToFirstPlay')
    jumpToTitleMenu = makeMachineOperation('jumpToTitleMenu')
    jumpToMenu = makeMachineOperation('jumpToMenu')
    jumpToManagerProgramChain = \
        makeMachineOperation('jumpToManagerProgramChain')

    # Timed jump
    setTimedJump = makeMachineOperation('setTimedJump')

    # Call and resume
    callFirstPlay = makeMachineOperation('callFirstPlay')
    callTitleMenu = makeMachineOperation('callTitleMenu')
    callMenu = makeMachineOperation('callMenu')
    callManagerProgramChain = \
        makeMachineOperation('callManagerProgramChain')
    resume = makeMachineOperation('resume')

    # Selectable streams
    setAngle = makeMachineOperation('setAngle')
    setAudio = makeMachineOperation('setAudio')
    setSubpicture = makeMachineOperation('setSubpicture')

    # Karaoke control
    setKaraokeMode = makeMachineOperation('setKaraokeMode')


    #
    # Registers
    #

    def getSystem0(self):
        """Return the value of system register 0 (menu_language)."""
        return strToIso639(self.prefMenuLang)

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
        return strToIso639(self.parentalCountry)

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
            self.generalRegisters.append(GeneralRegister())

        self.systemRegisters = []
        for i in range(24):
            self.systemRegisters.append( \
                SystemRegister(getattr(self, "getSystem%d" % i)))

    def getGeneralPurpose(self, regNr):
        """Return the object corresponding to the specified general
        purpose register."""
        assert 0 <= regNr <= 15
        return self.generalRegisters[regNr]

    def getSystemParameter(self, regNr):
        """Return the object corresponding to the specified system
        parameter."""
        assert 0 <= regNr <= 23
        return self.systemRegisters[regNr]


class DiscNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def nop(self):
        """No operation."""
        pass

    def exit(self):
        """End execution of the machine."""
        pass

    def jumpToTitle(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is provided with respect to the video
        manager, i.e. is global the whole disk."""
        pass

    def jumpToFirstPlay(self):
        """Jump to the first play program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in that
        disk when playback starts."""
        pass

    def jumpToTitleMenu(self):
        """Jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title menu."""

    def jumpToMenu(self, titleSetNr, titleNr, menuType):
        """Jump to menu 'menuType' in title 'titleNr' of video title
        set 'titleSetNr'.

        Specifying 0 as 'titleSetNr' chooses the video manager,
        i.e. the title number will be used to select a title from the
        video manager.

        The menu type is one of dvdread.MENU_TYPE_TITLE,
        dvdread.MENU_TYPE_ROOT, dvdread.MENU_TYPE_SUBPICTURE,
        dvdread.MENU_TYPE_AUDIO, dvdread.MENU_TYPE_ANGLE, and
        dvdread.MENU_TYPE_CHAPTER."""
        pass

    def jumpToManagerProgramChain(self, programChainNr):
        """Jump to the specified program chain in the video
        manager.

        Program chains directly associated to the video manager are
        only for menus."""
        pass

    def setTimedJump(self, programChainNr, seconds):
        """Sets the special purpose registers (SPRMs) 10 and 9 with
        'programChainNr' and 'seconds', respectively.

        SPRM 9 will be set with a time value in seconds and the
        machine decreases its value automatically every second. When
        the value reaches 0, an automatic jump to the video manager
        program chain stored in register 10 will happen."""
        pass

    def callFirstPlay(self, rtn=0):
        """Save the current location and jump to the first play
        program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in that
        disk when playback starts. If 'rtn' is not zero, it specifies
        the cell number to return to when the saved state is resumed."""
        pass

    def callTitleMenu(self, rtn=0):
        """Save the current location and jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title
        menu. If 'rtn' is not zero, it specifies the cell number to
        return to when the saved state is resumed."""
        pass

    def callManagerProgramChain(self, programChainNr, rtn=0):
        """Save the current location and jump to the specified program
        chain in the video manager.

        Program chains directly associated to the video manager are
        only for menus."""
        pass

    def resume(self):
        """Resume playback at the previously saved location."""
        pass


class TitleSetNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the container of the current program chain.

        Containers for program chains are either language units and
        video title sets."""
        pass

    def linkChapter(self, chapterNr):
        """Jump to the specified chapter in the current video title
        set.

        Chapters are a logical subdivision of video title sets. Each
        chapter is characterized by the program chain and program
        where it starts."""
        pass

    def jumpToTitleInSet(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is provided with respect to the current video
        title set."""
        pass

    def jumpToChapterInSet(self, titleNr, chapterNr):
        """Jump to the specified chapter in the specified title.

        The title number is provided with respect to the current video
        title set."""
        pass

    def callMenu(self, menuType, rtn=0):
        """Save the current location and jump to the menu of the
        specified type in the current title.

        The menu type is one of dvdread.MENU_TYPE_TITLE,
        dvdread.MENU_TYPE_ROOT, dvdread.MENU_TYPE_SUBPICTURE,
        dvdread.MENU_TYPE_AUDIO, dvdread.MENU_TYPE_ANGLE, and
        dvdread.MENU_TYPE_CHAPTER."""
        pass


class LangUnitNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the container of the current program chain.

        Containers for program chains are either language units and
        video title sets."""
        pass


class ProgramChainNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def linkTopCell(self):
        """Jump to beginning of the current cell."""
        pass

    def linkNextCell(self):
        """Jump to the beginning of the next cell."""
        pass

    def linkPrevCell(self):
        """Jump to the beginning of the previous cell."""
        pass

    def linkTopProgram(self):
        """Jump to the beginning of the current program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        pass

    def linkNextProgram(self):
        """Jump to the beginning of the next program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        pass

    def linkPrevProgram(self):
        """Jump to the beginning of the previous program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        pass

    def linkTopProgramChain(self):
        """Jump to the beginning of the current program chain."""
        pass

    def linkNextProgramChain(self):
        """Jump to the beginning of the next program chain."""
        pass

    def linkPrevProgramChain(self):
        """Jump to the beginning of the previous program chain."""
        pass

    def linkGoUpProgramChain(self):
        """Jump to the 'up' program chain.

        The 'up' program chain is explicitly referenced from a given
        program chain."""
        pass

    def linkTailProgramChain(self):
        """Jump to the end command block of the current program chain."""
        pass

    def linkProgram(self, programNr):
        """Jump to the specified program in the current program
        chain.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        pass

    def linkCell(self, cellNr):
        """Jump to the specified cell in the current program chain."""
        pass


class CommandBlockNavigator(object):
    __slots__ = ('machine',
                 'decoder')

    def __init__(self, machine):
        self.machine = machine
        self.decoder = decode.CommandDecoder(PerformMachine(machine))

    def goto(self, commandNr):
        """Go to command 'commandNr' in the current command block."""
        pass

    def brk(self):
        """Terminate executing (break from) the current command block."""
        pass

    def openSetParentalLevel(self, cmd):
        """Try to set parental level.

        If successful, jump to the specified command."""
        pass


class CellPlayer(object):
    """A player for DVD cells."""

    __slots__ = ('perform',
                 'cell',	# Cell currently being played.
                 'domain',	# Playback domain this cell belongs to.
                 'titleNr',	# DVD title number the cell is in.
                 'sectorNr',	# Last sector played.
                 'nav')		# Last nav packet seen.

    def __init__(self, perform):
        self.perform = perform
        self.cell = None
        self.domain = None
        self.titleNr = None
        self.sectorNr = None
        self.nav = None

    @restartPoint
    def playCell(self, cell):
        """Play the specified cell."""
        self.cell = cell

        # Find the playback domain for the cell.
        if isinstance(cell.programChain.container, dvdread.LangUnit):
            self.domain = dvdread.DOMAIN_MENU
        else:
            self.domain = dvdread.DOMAIN_TITLE

        # Find the DVD title number for the cell.
        if isinstance(cell.programChain.container, dvdread.LangUnit):
            self.titleNr = cell.programChain.container.container.titleSetNr
        elif isinstance(cell.programChain.container, dvdread.VideoTitleSet):
            self.titleNr = cell.programChain.container.titleSetNr
        elif isinstance(cell.programChain.container, dvdread.VideoManager):
            self.titleNr = 0
        else:
            assert False, 'Unexpected type for program chain container'        

        # Just play the first VOBU in the cell.
        yield Chain(self.playVobu(cell.firstSector))

    @restartPoint
    def playVobu(self, sectorNr):
        """Play the VOBU at the specified sector number."""
        self.sectorNr = sectorNr

        # Instruct the pipeline to play starting at the specified
        # sector.
        yield (self.domain, self.titleNr, sectorNr)

        # The values in the next nav packet should determine if more
        # material is played in the cell. See the 'setNav' method in
        # this class.

    def setNav(self, nav):
        """Set the new navigation packet."""
        self.nav = nav

        # Play the next VOBU.
        if nav.nextVOBU != 0x3fffffff:
            yield Restart.playVobu(self.sectorNr + nav.nextVOBU)


    #
    # Command Execution
    #

    def selectButton(self, buttonNr):
        """Select the specified button in the current menu."""
        pass

    def setSystemParam8(self, value):
        """Select the button specified by the 6 most significant bits
        of the 16 value 'value'."""
        pass

    def saveLocation(self, rtn=0):
        """Save the current location in the resume location.

        If 'rtn' is not zero, it specifies the cell number to return
        to when the saved state is resumed."""
        pass

    def setAngle(self, angle):
        """Set the current angle to the specified angle number."""
        pass

    def setAudio(self, audio):
        """Set the current audio stream as specified."""
        pass

    def setSubpicture(self, subpicture):
        """Set the current subpicture stream as specified."""
        pass

    def setKaraokeMode(self, mode):
        """Set the karaoke mode."""
        pass


    #
    # Playback Control
    #

    def jump(self, subdiv):
        pass

    def stop(self):
        pass

    def prevProgram(self):
        pass

    def nextProgram(self):
        pass


    #
    # Time Based Navigation
    #

    def getCurrentTime(self):
        pass
    currentTime = property(getCurrentTime)

    def getCanTimeJump(self):
        pass
    canTimeJump = property(getCanTimeJump)

    def timeJump(self, seconds):
        pass
    timeJump = synchronized(timeJump)

    def timeJumpRelative(self, seconds):
        pass
    timeJumpRelative = synchronized(timeJumpRelative)


    #
    # Stream Control
    #

    def getAudioStream(self):
        pass

    def setAudioStream(self, logical):
        pass
    audioStream = property(getAudioStream, setAudioStream)

    def getAudioStreams(self):
        pass


    #
    # Button Navigation
    #

    def setButtonNav(self, buttonNav):
        pass

    def getButtonObj(self):
        pass

    def selectButtonInteractive(self, buttonNr):
        pass

    def up(self):
        pass
    up = synchronized(up)

    def down(self):
        pass
    down = synchronized(down)

    def left(self):
        pass
    left = synchronized(left)

    def right(self):
        pass
    right = synchronized(right)

    def confirm(self):
        pass
    confirm = synchronized(confirm)

    def menu(self):
        pass
    menu = synchronized(menu)

    def rtn(self):
        pass
    rtn = synchronized(rtn)

    def force(self):
        pass


class VirtualMachine(object):
    """A DVD playback virtual machine implementation."""

    __slots__ = ('info',
                 'src',
                 'lock',
                 'perform',
                 'sched')

    def __init__(self, info, src):
        self.info = info
        self.src = src

        # The synchronized method lock.
        self.lock = threading.RLock()

        # Connect our signals to the source object.
        src.connect('vobu-read', self.vobuRead)
        src.connect('vobu-header', self.vobuHeader)

        # The perform machine.
        self.perform = PerformMachine()

        # Initialize the scheduler.
        self.sched = Scheduler(CellPlayer(self.perform).playCell(self.info.videoManager.getVideoTitleSet(1).getProgramChain(1).getCell(1)))

    #
    # Signal Handling
    #

    @synchronized
    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU."""

        try:
            # Get the next item.
            item = self.sched.next()
        except StopIteration:
            # Time to stop the pipeline.
            self.src.set_eos()
            self.src.emit('push-event', gst.Event(gst.EVENT_EOS));
            return
        except:
            # We had an exception in the playback code.
            traceback.print_exc()
            sys.exit(1)

        if isinstance(item, gst.Event):
            # We have an event, put it in the pipeline.
            self.src.emit('push-event', item);
        else:
            # Otherwise, we have a new playback position in the disc.
            (domain, titleNr, sectorNr) = item
            src.set_property('domain', domain)
            src.set_property('title', titleNr)
            src.set_property('vobu-start', sectorNr)

    @synchronized
    def vobuHeader(self, src, buf):
        """Invoked by the source element when it sees a VOBU
        header."""
        nav = dvdread.NavPacket(buf.get_data())
        self.sched.call(self.sched.setNav(nav))

    def flushSource(self):
        """Stop the source element. This operation works even in the
        middle of a VOBU playback and its necessary for fast
        interactive response."""
        self.src.set_property('block-count', 0)
