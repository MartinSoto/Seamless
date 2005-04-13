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

"""Main implementation of the DVD virtual machine."""

import string
import sys
import threading
import time
import traceback

import gst

import itersched
from itersched import NoOp, Call, Chain, Restart, restartPoint

import dvdread
import decode
import disassemble
import events


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


class MachineStill(object):
    """A token to tell the machine's scheduling loop that we are
    displaying a still frame."""

    __slots__ = ()

# The single MachineStillCls instance.
machineStill = MachineStill()


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

        yield NoOp


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
    def restartOp(self, *args, **keywords):
        yield getattr(Restart, method)(*args, **keywords)

    return restartOp

# FIXME: Erase this when all operations get implemented properly.
def makeDummyOperation(method):
    def printOp(self, *args, **keywords):
        lArgs = [repr(i) for i in args]
        lKw = ['%s=%s' % (name, str(value))
               for name, value in keywords.items()]
        print "Invoked: %s(%s)" % (method, string.join(lArgs + lKw, ', '))
        yield NoOp

    return printOp


class PerformMachine(object):
    __slots__ = ('info',
                 'location',

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
                 'systemRegisters',

                 'currentNav')

    def __init__(self, info, location=None):
        self.info = info
        self.location = location

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

        # Initialize all machine registers.
        self.generalRegisters = None
        self.systemRegisters = None
        self.initializeRegisters()

        # The current navigation packet.
        self.currentNav = None

    def setLocation(self, location):
        self.location = location


    #
    # Machine Operations
    #

    # Basic operations.
    def nop(self):
        """No operation."""
        yield NoOp

    goto = makeMachineOperation('goto')
    brk = makeMachineOperation('brk')
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
    selectButton = makeDummyOperation('selectButton')
    setSystemParam8 = makeDummyOperation('selectButton')

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
    def setTimedJump(self, programChainNr, seconds):
        """Sets the special purpose registers (SPRMs) 10 and 9 with
        'programChainNr' and 'seconds', respectively.

        SPRM 9 will be set with a time value in seconds and the
        machine decreases its value automatically every second. When
        the value reaches 0, an automatic jump to the video manager
        program chain stored in register 10 will happen."""
        # FIXME: Implement this.
        print 'setTimeJump attempted, implement me!' 
        yield NoOp

    # Call and resume
    def callFirstPlay(self, rtn=0):
        """Save the current location and jump to the first play
        program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in the
        disk when playback starts. If 'rtn' is not zero, it specifies
        the cell number to return to when the saved state is resumed."""
        yield Call(DiscPlayer(self, True).jumpToFirstPlay())

        yield Chain(self.finishCallOp(rtn))

    def callTitleMenu(self, rtn=0):
        """Save the current location and jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title
        menu. If 'rtn' is not zero, it specifies the cell number to
        return to when the saved state is resumed."""
        yield Call(DiscPlayer(self, True).jumpToTitleMenu())

        yield Chain(self.finishCallOp(rtn))

    def callManagerProgramChain(self, programChainNr, rtn=0):
        """Save the current location and jump to the specified program
        chain in the video manager. If 'rtn' is not zero, it specifies
        the cell number to return to when the saved state is resumed.

        Program chains directly associated to the video manager are
        only for menus."""
        yield Call(DiscPlayer(self, True). \
                   jumpToManagerProgramChain(programChainNr))

        yield Chain(self.finishCallOp(rtn))

    def callMenu(self, menuType, rtn=0):
        """Save the current location and jump to the menu of the
        specified type in the current title. If 'rtn' is not zero, it
        specifies the cell number to return to when the saved state is
        resumed.

        The menu type is one of dvdread.MENU_TYPE_TITLE,
        dvdread.MENU_TYPE_ROOT, dvdread.MENU_TYPE_SUBPICTURE,
        dvdread.MENU_TYPE_AUDIO, dvdread.MENU_TYPE_ANGLE, and
        dvdread.MENU_TYPE_CHAPTER."""
        title = self.location.currentTitle()
        yield Call(DiscPlayer(self, True). \
                   jumpToMenu(title.videoTitleSet.titleSetNr,
                              title.titleNr, menuType))

        yield Chain(self.finishCallOp(rtn))

    def finishCallOp(self, rtn):
        """Perform the final, common part of a call operation."""
        # If a program chain is playing, update the color lookup
        # table.
        programChain = self.location.currentProgramChain()
        if programChain != None:
            yield Call(events.subpictureClutEvent(programChain))

        if rtn != 0:
            yield Restart.playCell(rtn)

    resume = makeMachineOperation('resume')

    # Selectable streams
    def setAngle(self, angle):
        """Set the current angle to the one specified."""
        # FIXME: Implement this.
        yield NoOp
    
    def setAudio(self, logical):
        """Set the current logical audio stream to the one specified."""
        programChain = self.location.currentProgramChain()
        if programChain == None or self.audio == 15:
            # We aren't playing a program chain, or the logical audio
            # track is explicitly set to none.
            physical = -1
        elif isinstance(programChain.container, dvdread.LangUnit):
            # We are in the menu domain. The physical audio is always
            # 0.
            physical = 0
        else:
            # Try to find a physical stream from the information in
            # the program chain.
            physical = programChain.getAudioPhysStream(self.audio + 1)
            if physical == None:
                # Just pick the first existing stream.
                physical = -1
                for logical in range(1, 9):
                    newPhys = self.location.programChain. \
                              getAudioPhysStream(logical)
                    if newPhys != None:
                        physical = newPhys
                        break

        print "*** Setting physical audio to", physical
        yield Chain(events.audioEvent(physical))

    def setSubpicture(self, logical):
        """Set the current logical subpicture stream to the one
        specified."""
        programChain = self.location.currentProgramChain()
        if programChain == None or \
           self.subpicture & 0x40 == 0 or \
           self.subpicture & 0x3f > 31:
            # We aren't playing a program chain, or the logical
            # subpicture is explicitly set to none.
            physical = -1
        elif isinstance(programChain.container, dvdread.LangUnit):
            # We are in the menu domain. The physical subpicture is
            # always 0.
            physical = 0
        else:
            streams = self.location.programChain. \
                      getSubpicturePhysStreams((self.subpicture \
                                                & 0x1f) + 1)
            if streams == None:
                physical = -1
            else:
                if self.location.getAttributeContainer(). \
                   videoAttributes.aspectRatio == dvdread.ASPECT_RATIO_4_3:
                    physical = streams[dvdread.SUBPICTURE_PHYS_TYPE_4_3]
                else:
                    if self.aspectRatio == dvdread.ASPECT_RATIO_16_9:
                        physical = streams[dvdread. \
                                           SUBPICTURE_PHYS_TYPE_WIDESCREEN]
                    else:
                        physical = streams[dvdread. \
                                           SUBPICTURE_PHYS_TYPE_LETTERBOX]

        print "*** Setting physical subpicture to", physical
        yield Chain(events.subpictureEvent(physical))

    # Karaoke control
    setKaraokeMode = makeDummyOperation('setKaraokeMode')


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
        title = self.location.currentTitle()
        if title != None:
            return title.globalTitleNr
        else:
            return 0

    def getSystem5(self):
        """Return the value of system register 5 (title_in_vts)."""
        title = self.location.currentTitle()
        if title != None:
            return title.titleNr
        else:
            return 0

    def getSystem6(self):
        """Return the value of system register 6 (program_chain)."""
        programChain = self.location.currentProgramChain()
        if programChain != None:
            return programChain.programChainNr
        else:
            return 0

    def getSystem7(self):
        """Return the value of system register 7 (chapter)."""
        cell = self.location.currentCell()
        if cell != None:
            return cell.programNr
        else:
            return 0

    def getSystem8(self):
        """Return the value of system register 8 (highlighted_button)."""
        return self.location.button << 10

    def getSystem9(self):
        """Return the value of system register 9 (navigation_timer)."""
        # FIXME: implement this.
        print >> sys.stderr, "Navigation timer checked, implement me!"
        return 0

    def getSystem10(self):
        """Return the value of system register 10 (program_chain_for_timer)."""
        # FIXME: implement this.
        print >> sys.stderr, "Navigation timer checked, implement me!"
        return 0

    def getSystem11(self):
        """Return the value of system register 11 (karaoke_mode)."""
        # FIXME: implement this.
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


    #
    # Language Units
    #

    def getLangUnit(self, container):
        """Find the appropriate language unit for a container.

        Given a container (video manager or title set) this method
        returns an appropriate language unit. If there's a language
        unit for the preferred menu language set in this object, it is
        returned. Otherwise, the first one available is returned."""
        unit = container.getLangUnit(self.prefMenuLang)
        if unit == None:
            unit = container.getLangUnit(1)

        return unit


class DiscPlayer(object):
    __slots__ = ('perform',
                 'callOp',
                 'videoManager')

    def __init__(self, perform, callOp=False):
        """Create a disc player, based on the given perform machine.

        'callOp' must be set to 'True' when the disc player is created
        as part of a call operation. Otherwise the resume command will
        continue playback by jumping to the first play program chain."""
        self.perform = perform
        self.callOp = callOp

        self.videoManager = self.perform.info.videoManager

    @restartPoint
    def jumpToFirstPlay(self):
        """Jump to the first play program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in that
        disk when playback starts."""
        yield Call(ProgramChainPlayer(self.perform). \
                   playProgramChain(self.videoManager.firstPlay))

    @restartPoint
    def jumpToTitle(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is provided with respect to the video
        manager, i.e. is global to the whole disk."""
        title = self.videoManager.getVideoTitle(titleNr)
        yield Call(TitlePlayer(self.perform).playTitle(title))

    @restartPoint
    def jumpToTitleMenu(self):
        """Jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title menu."""
        langUnit = self.perform.getLangUnit(self.videoManager)
        yield Call(LangUnitPlayer(self.perform). \
                   playMenuInUnit(langUnit, dvdread.MENU_TYPE_TITLE))

    @restartPoint
    def jumpToManagerProgramChain(self, programChainNr):
        """Jump to the specified program chain in the video
        manager.

        Program chains directly associated to the video manager are
        only for the menus."""
        langUnit = self.perform.getLangUnit(self.videoManager)
        yield Call(LangUnitPlayer(self.perform). \
                   playProgramChainInUnit(langUnit, programChainNr))

    @restartPoint
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
        # Get the title set and title. Title set 0 is the video manager.
        if titleSetNr == 0:
            titleSet = self.videoManager
        else:
            titleSet = self.videoManager.getVideoTitleSet(titleSetNr)

        title = titleSet.getVideoTitle(titleNr)

        yield Call(TitlePlayer(self.perform). \
                   playMenuInTitle(title, menuType))

    @restartPoint
    def resume(self):
        """Resume playback at the previously saved location."""
        if self.callOp:
            # We are handling a resume from an actual call
            # operation. Just let the caller go on.
            yield NoOp
        else:
            # A resume happened when no call operation was in
            # effect. Try to keep playing.
            yield Chain(self.jumpToFirstPlay())

    @restartPoint
    def exit(self):
        """End execution of the machine."""
        # Returning without doing anything is enough to do the trick.
        yield NoOp


class TitlePlayer(object):
    __slots__ = ('perform',
                 'title')

    def __init__(self, perform):
        self.perform = perform

        self.title = None

    def currentTitle(self):
        """Return the title currently being played.

        'None' is returned if no title is currently being played."""
        return self.title

    @restartPoint
    def playTitle(self, title, chapterNr=1):
        """Play the specified chapter of the given video title."""
        self.title = title

        yield Chain(self.linkChapter(chapterNr))

    @restartPoint
    def playMenuInTitle(self, title, menuType):
        """Make the given video title current, and jump inmediatly to
        the corresponding menu of the specified menu type.

        This operation is necessary to implement a particular DVD
        virtual machine command that selects a menu in the context of
        a particular video title."""
        self.title = title

        langUnit = self.perform.getLangUnit(self.title.videoTitleSet)
        yield Call(LangUnitPlayer(self.perform). \
                   playMenuInUnit(langUnit, menuType))

    @restartPoint
    def linkChapter(self, chapterNr):
        """Jump to the specified chapter in the current video title.

        Chapters are a logical subdivision of video title sets. Each
        chapter is characterized by the program chain and program
        where it starts."""
        chapter = self.title.getChapter(chapterNr)
        yield Call(ProgramChainPlayer(self.perform). \
                   playProgramChain(chapter.cell.programChain,
                                    chapter.cell.cellNr))

    @restartPoint
    def jumpToTitleInSet(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is given with respect to the current video
        title set (i.e., the title set the current title belongs to.)"""
        yield Chain(self.jumpToChapterInSet(titleNr, 1))

    @restartPoint
    def jumpToChapterInSet(self, titleNr, chapterNr):
        """Jump to the specified chapter in the specified title.

        The title number is provided with respect to the current video
        title set (i.e., the title set the current title belongs to.)"""
        title = self.title.videoTitleSet.getVideoTitle(titleNr)
        yield Chain(self.playTitle(title, chapterNr))

    @restartPoint
    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the current title."""
        programChain = self.title.getProgramChain(programChainNr)
        yield Call(ProgramChainPlayer(self.perform). \
                   playProgramChain(programChain))


class LangUnitPlayer(object):
    __slots__ = ('perform',
                 'unit')

    def __init__(self, perform):
        self.perform = perform

        self.unit = None

    @restartPoint
    def playMenuInUnit(self, unit, menuType):
        """Play the menu of the specified menu type in the given
        language unit."""
        self.unit = unit

        yield Call(ProgramChainPlayer(self.perform). \
                   playProgramChain(self.unit.getMenuProgramChain(menuType)))

    @restartPoint
    def playProgramChainInUnit(self, unit, programChainNr):
        """Play the specified program chain in the given language
        unit."""
        self.unit = unit

        yield Chain(self.linkProgramChain(programChainNr))

    @restartPoint
    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the current language unit."""
        programChain = self.unit.getProgramChain(programChainNr)
        yield Call(ProgramChainPlayer(self.perform). \
                   playProgramChain(programChain))


class ProgramChainPlayer(object):
    __slots__ = ('perform',
                 'programChain',
                 'cell')

    def __init__(self, perform):
        self.perform = perform
        self.programChain = None
        self.cell = None

    def currentProgramChain(self):
        """Return the program chain currently being played.

        'None' is returned if no program chain is currently being
        played."""
        return self.programChain

    @restartPoint
    def playProgramChain(self, programChain, cellNr=1):
        """Play the specified program chain.

        'cellNr' specifies the start cell."""
        self.programChain = programChain
        self.cell = None

        # Update the color lookup table.
        yield Call(events.subpictureClutEvent(self.programChain))

        if cellNr == 1:
            # Play the 'pre' commands.
            yield Call(CommandBlockPlayer(self.perform). \
                       playBlock(self.programChain.preCommands))

        # Go to the specified cell.
        yield Chain(self.linkCell(cellNr))

    @restartPoint
    def linkCell(self, cellNr):
        """Jump to the specified cell in the current program chain."""
        assert 1 <= cellNr <= self.programChain.cellCount

        self.cell = self.programChain.getCell(cellNr)

        # Play the cell.
        yield Call(CellPlayer(self.perform).playCell(self.cell))

        # Play the corresponding cell commands.
        if self.cell.commandNr != 0:
            yield Call(CommandBlockPlayer(self.perform). \
                       playBlock(self.programChain.cellCommands,
                                 self.cell.commandNr))

        if cellNr == self.programChain.cellCount:
            # No more cells. Play the "tail".
            yield Chain(self.linkTailProgramChain())
        else:
            # Keep playing cells.
            yield Chain(self.linkCell(cellNr + 1))

    @restartPoint
    def linkTopCell(self):
        """Jump to the beginning of the current cell."""
        yield Chain(self.linkCell(self.cell.cellNr))

    @restartPoint
    def linkNextCell(self):
        """Jump to the beginning of the next cell."""
        yield Chain(self.linkCell(self.cell.cellNr + 1))

    @restartPoint
    def linkPrevCell(self):
        """Jump to the beginning of the previous cell."""
        yield Chain(self.linkCell(self.cell.cellNr - 1))

    @restartPoint
    def linkProgram(self, programNr):
        """Jump to the specified program in the current program
        chain.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        yield Chain(self.linkCell(self.programChain. \
                                  getProgramCell(programNr).cellNr))

    @restartPoint
    def linkTopProgram(self):
        """Jump to the beginning of the current program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        programNr = self.cell.programNr
        yield Chain(self.linkProgram(programNr))

    @restartPoint
    def linkNextProgram(self):
        """Jump to the beginning of the next program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        programNr = self.cell.programNr
        yield Chain(self.linkProgram(programNr + 1))

    @restartPoint
    def linkPrevProgram(self):
        """Jump to the beginning of the previous program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        programNr = self.cell.programNr
        yield Chain(self.linkProgram(programNr - 1))

    @restartPoint
    def linkTopProgramChain(self):
        """Jump to the beginning of the current program chain."""
        yield Chain(self.playProgramChain(self.programChain))

    @restartPoint
    def linkNextProgramChain(self):
        """Jump to the beginning of the next program chain."""
        yield Chain(self.playProgramChain(self.programChain.nextProgramChain))

    @restartPoint
    def linkPrevProgramChain(self):
        """Jump to the beginning of the previous program chain."""
        yield Chain(self.playProgramChain(self.programChain.prevProgramChain))

    @restartPoint
    def linkGoUpProgramChain(self):
        """Jump to the 'up' program chain.

        The 'up' program chain is explicitly referenced from a given
        program chain."""
        yield Chain(self.playProgramChain(self.programChain.goUpProgramChain))

    @restartPoint
    def linkTailProgramChain(self):
        """Jump to the end command block of the current program chain."""
        self.cell = None

        # Play the "post" commands.
        yield Call(CommandBlockPlayer(self.perform). \
                   playBlock(self.programChain.postCommands))

        # If there's a next program chain, link to it.
        next = self.programChain.nextProgramChain
        if next != None:
            yield Chain(self.playProgramChain(next))


class CommandBlockPlayer(object):
    __slots__ = ('perform',
                 'decoder',
                 'commands',
                 'commandNr')

    def __init__(self, perform):
        self.perform = perform

        self.decoder = decode.CommandDecoder(perform)

        self.commands = None
        self.commandNr = 0

    @restartPoint
    def playBlock(self, commands, commandNr=1):
        self.commands = commands
        yield Chain(self.goto(commandNr))

    @restartPoint
    def goto(self, commandNr):
        """Go to command 'commandNr' in the current command block."""
        assert commandNr > 0

        self.commandNr = commandNr

        while self.commandNr <= self.commands.count:
            # Actually perform the command.
            print disassemble.disassemble(self.commands.get(self.commandNr),
                                          pos=self.commandNr)
            yield Call(self.decoder.performCommand( \
                self.commands.get(self.commandNr)))

            self.commandNr += 1

    @restartPoint
    def brk(self):
        """Terminate executing (break from) the current command block."""
        # Just doing nothing should do the trick :-)
        yield NoOp

    @restartPoint
    def openSetParentalLevel(self, commandNr):
        """Try to set parental level.

        If successful, jump to the specified command."""
        # FIXME: implement this.
        print "Attempt to set parental level, implement me!"

        # For the moment, just jump inconditionally.
        yield Chain(self.goto(commandNr))


class CellPlayer(object):
    """A player for DVD cells."""

    __slots__ = ('perform',
                 'cell',	# Cell currently being played.
                 'domain',	# Playback domain this cell belongs to.
                 'titleNr',	# DVD title number the cell is in.
                 'sectorNr')	# Last sector played.

    def currentCell(self):
        """Return the cell currently being played.

        'None' is returned if no cell is currently being played."""
        return self.cell

    def __init__(self, perform):
        self.perform = perform
        self.cell = None
        self.domain = None
        self.titleNr = None
        self.sectorNr = None

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
        yield Chain(self.playFromVobu(cell.firstSector))

    @restartPoint
    def playFromVobu(self, sectorNr):
        """Play the VOBU at the specified sector number."""
        self.sectorNr = sectorNr

        # Play until the end of the cell.
        nav = None
        while True:
            yield (self.domain, self.titleNr, self.sectorNr)

            # After the yield, the whole VOBU will be read by the
            # playback element and sent down the pipeline. During this
            # process, a new nav packed (VOBU header) will be seen and
            # stored in the perform object.

            # At this point, a new nav packet must be there. If this
            # is not the case, we have a serious problem.
            assert nav != self.perform.currentNav

            nav = self.perform.currentNav
            if nav.nextVobu != 0x3fffffff:
                # Progress to the next VOBU.
                self.sectorNr = self.sectorNr + nav.nextVobu
            else:
                # We reached the end of the cell.
                break

        print "*** Still time: ", self.cell.stillTime

        if self.cell.stillTime > 0:
            # We have a still frame.

            if self.cell.stillTime == 0xff:
                # Unlimited wait time. Loop "infinitely" until a
                # restart operation takes this method out of the
                # stack.
                while True:
                    yield machineStill
            else:
                # Wait the specified number of seconds.
                endTime = time.time() + self.cell.stillTime
                while time.time() < endTime:
                    yield machineStill


class PlaybackLocation(object):
    """A class encapsulating operations necessary to determine the
    location in the dvd structure that is currently being played back."""
    
    __slots__ = ('sched',)

    def __init__(self, sched):
        self.sched = sched

    def getValue(self, methodName):
        for inst in self.sched.restartable():
            if hasattr(inst, methodName):
                return getattr(inst, methodName)()
        return None

    def currentTitle(self):
        return self.getValue('currentTitle')

    def currentProgramChain(self):
        return self.getValue('currentProgramChain')

    def currentCell(self):
        return self.getValue('currentCell')


def synchronized(method):
    """Wrapper for syncronized methods."""

    def wrapper(self, *args, **keywords):
        self.lock.acquire()
        try:
            method(self, *args, **keywords)
        finally:
            self.lock.release()

    return wrapper


def entryPoint(method):
    def wrapper(self, *args, **keywords):
        self.sched.call(method(self, *args, **keywords))

    return synchronized(wrapper)


class VirtualMachine(object):
    """A DVD playback virtual machine implementation."""

    __slots__ = ('info',
                 'src',
                 'lock',
                 'perform',
                 'sched',
                 'location')

    def __init__(self, info, src):
        self.info = info
        self.src = src

        # The synchronized method lock.
        self.lock = threading.RLock()

        # Connect our signals to the source object.
        src.connect('vobu-read', self.vobuRead)
        src.connect('vobu-header', self.vobuHeader)

        # The perform machine.
        self.perform = PerformMachine(info)

        # Initialize the scheduler. The initial object should play the
        # first play program chain.
        self.sched = itersched.Scheduler(DiscPlayer(self.perform). \
                                         jumpToFirstPlay())

        # The location is based on the current state of the scheduler.
        self.location = PlaybackLocation(self.sched)
        self.perform.setLocation(self.location)


    #
    # Signal Handling
    #

    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU.

        Synchronization is managed internally by this method."""

        self.lock.acquire()
        
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
        elif item == machineStill:
            # We are displaying a still frame. Keep the pipeline busy,
            # but be nice to the processor:

            # We don't want to keep the lock while sleeping.
            self.lock.release()

            time.sleep(0.1)

            self.src.emit('push-event', gst.Event(gst.EVENT_FILLER))

            return
        else:
            # Otherwise, we have a new playback position in the disc.
            (domain, titleNr, sectorNr) = item
            src.set_property('domain', domain)
            src.set_property('title', titleNr)
            src.set_property('vobu-start', sectorNr)

        self.lock.release()

    @synchronized
    def vobuHeader(self, src, buf):
        """The signal handler for the source's vobu-header signal."""
        # This must be done inmediatly. Otherwise, the contents of the
        # buffer may change before we handle them.
        nav = dvdread.NavPacket(buf.get_data())

        # Store the navigation packet as part of the state.
        self.perform.currentNav = nav

        # Send a nav event. This event cannot be queued and must be
        # sent inmediatly after receiving the header.
        self.src.emit('push-event', events.navEvent(nav))

    def flushSource(self):
        """Stop the source element. This operation works even in the
        middle of a VOBU playback and it's necessary for fast
        interactive response."""
        self.src.set_property('block-count', 0)


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

    def timeJumpRelative(self, seconds):
        pass


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

    def down(self):
        pass

    def left(self):
        pass

    def right(self):
        pass

    def confirm(self):
        pass

    def menu(self):
        pass

    def rtn(self):
        pass

    def force(self):
        pass

