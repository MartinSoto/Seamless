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

import sys
import string
import copy
import time
import traceback
import threading

from dvdread import *
import decode
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


# A command disassembler for debugging.
disasm = disassemble.CommandDisassembler()


def synchronized(method):
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


class DiscNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def nop(self):
        """No operation."""
        pass

    def exit(self):
        """End execution of the machine."""
        # FIXME
        print >> sys.stderr, "Machine exited"

    def jumpToTitle(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is provided with respect to the video
        manager, i.e. is global the whole disk."""
        self.location.jumpToUnit(self.info.videoManager.getVideoTitle(titleNr))

    def jumpToFirstPlay(self):
        """Jump to the first play program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in that
        disk when playback starts."""
        self.location.jumpToUnit(self.info.videoManager.firstPlay)

    def jumpToTitleMenu(self):
        """Jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title menu."""
        langUnit = self.getLangUnit(self.info.videoManager)
        self.location.jumpToUnit(langUnit.getMenuProgramChain(MENU_TYPE_TITLE))

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
        # Get the title set. Title set 0 is the video manager.
        if titleSetNr == 0:
            titleSet = self.info.videoManager
        else:
            titleSet = self.info.videoManager.getVideoTitleSet(titleSetNr)

        # Jump first to the video title to make sure that the location
        # points to the right title.
        title = titleSet.getVideoTitle(titleNr)
        self.location.jumpToUnit(title)
        
        # Now jump to the actual program chain corresponding to the menu.
        langUnit = self.getLangUnit(title.videoTitleSet)
        self.location.jumpToUnit(langUnit.getMenuProgramChain(menuType))

    def jumpToManagerProgramChain(self, programChainNr):
        """Jump to the specified program chain in the video
        manager.

        Program chains directly associated to the video manager are
        only for menus."""
        langUnit = self.getLangUnit(self.info.videoManager)
        self.location.jumpToUnit(langUnit.getProgramChain(programChainNr))

    def setTimedJump(self, programChainNr, seconds):
        """Sets the special purpose registers (SPRMs) 10 and 9 with
        'programChainNr' and 'seconds', respectively.

        SPRM 9 will be set with a time value in seconds and the
        machine decreases its value automatically every second. When
        the value reaches 0, an automatic jump to the video manager
        program chain stored in register 10 will happen."""
        print >> sys.stderr, "Timed jump, implement me!"

    def callFirstPlay(self, rtn=0):
        """Save the current location and jump to the first play
        program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in that
        disk when playback starts. If 'rtn' is not zero, it specifies
        the cell number to return to when the saved state is resumed."""
        self.saveLocation(rtn)
        self.jumpToFirstPlay()

    def callTitleMenu(self, rtn=0):
        """Save the current location and jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title
        menu. If 'rtn' is not zero, it specifies the cell number to
        return to when the saved state is resumed."""
        self.saveLocation(rtn)
        self.jumpToTitleMenu()

    def callManagerProgramChain(self, programChainNr, rtn=0):
        """Save the current location and jump to the specified program
        chain in the video manager.

        Program chains directly associated to the video manager are
        only for menus."""
        self.saveLocation(rtn)
        self.jumpToManagerProgramChain(programChainNr)

    def resume(self):
        """Resume playback at the previously saved location."""
        if self.resumeLocation == None:
            raise PlayerException, "Attempt to resume with no resume info"

        # We set the current location to allow for it to continue
        # playback from the resume point.
        self.location.set(self.resumeLocation)
        self.resumeLocation = None

        self.updatePipeline()


class TitleSetNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the container of the current program chain.

        Containers for program chains are either language units and
        video title sets."""
        self.location.jumpToUnit(self.location.programChain.container. \
                                 getProgramChain(programChainNr))

    def linkChapter(self, chapterNr):
        """Jump to the specified chapter in the current video title
        set.

        Chapters are a logical subdivision of video title sets. Each
        chapter is characterized by the program chain and program
        where it starts."""
        self.location.jumpToUnit(self.location.title.getChapter(chapterNr))

    def jumpToTitleInSet(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is provided with respect to the current video
        title set."""
        self.location.jumpToUnit(self.location.title.videoTitleSet. \
                                 getVideoTitle(titleNr))

    def jumpToChapterInSet(self, titleNr, chapterNr):
        """Jump to the specified chapter in the specified title.

        The title number is provided with respect to the current video
        title set."""
        self.location.jumpToUnit(self.location.title.videoTitleSet. \
                                 getVideoTitle(titleNr).getChapter(chapterNr))

    def callMenu(self, menuType, rtn=0):
        """Save the current location and jump to the menu of the
        specified type in the current title.

        The menu type is one of dvdread.MENU_TYPE_TITLE,
        dvdread.MENU_TYPE_ROOT, dvdread.MENU_TYPE_SUBPICTURE,
        dvdread.MENU_TYPE_AUDIO, dvdread.MENU_TYPE_ANGLE, and
        dvdread.MENU_TYPE_CHAPTER."""
        self.saveLocation(rtn)
        titleSetNr = self.location.title.videoTitleSet.titleSetNr
        titleNr = self.location.title.titleNr
        self.jumpToMenu(titleSetNr, titleNr, menuType)


class LangUnitNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the container of the current program chain.

        Containers for program chains are either language units and
        video title sets."""
        self.location.jumpToUnit(self.location.programChain.container. \
                                 getProgramChain(programChainNr))


class ProgramChainNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def linkTopCell(self):
        """Jump to beginning of the current cell."""
        self.location.jumpToUnit(self.location.cell)

    def linkNextCell(self):
        """Jump to the beginning of the next cell."""
        self.location.jumpToUnit(self.location.programChain. \
                                 getCell(self.location.cell.cellNr + 1))

    def linkPrevCell(self):
        """Jump to the beginning of the previous cell."""
        self.location.jumpToUnit(self.location.programChain. \
                                 getCell(self.location.cell.cellNr - 1))

    def linkTopProgram(self):
        """Jump to the beginning of the current program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        programNr = self.location.cell.programNr
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr))

    def linkNextProgram(self):
        """Jump to the beginning of the next program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        programNr = self.location.cell.programNr
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr + 1))

    def linkPrevProgram(self):
        """Jump to the beginning of the previous program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        programNr = self.location.cell.programNr
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr - 1))

    def linkTopProgramChain(self):
        """Jump to the beginning of the current program chain."""
        self.location.jumpToUnit(self.location.programChain)

    def linkNextProgramChain(self):
        """Jump to the beginning of the next program chain."""
        self.location.jumpToUnit(self.location.programChain.nextProgramChain)

    def linkPrevProgramChain(self):
        """Jump to the beginning of the previous program chain."""
        self.location.jumpToUnit(self.location.programChain.prevProgramChain)

    def linkGoUpProgramChain(self):
        """Jump to the 'up' program chain.

        The 'up' program chain is explicitly referenced from a given
        program chain."""
        self.location.jumpToUnit(self.location.programChain.goUpProgramChain)

    def linkTailProgramChain(self):
        """Jump to the end command block of the current program chain."""
        self.location.setCommand(COMMAND_POST)

    def linkProgram(self, programNr):
        """Jump to the specified program in the current program
        chain.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        self.location.jumpToUnit(self.location.programChain. \
                                 getProgramCell(programNr))

    def linkCell(self, cellNr):
        """Jump to the specified cell in the current program chain."""
        self.location.jumpToUnit(self.location.programChain.getCell(cellNr))


class CommandBlockNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine

    def goto(self, commandNr):
        """Go to command 'commandNr' in the current command block."""
        self.location.commandNr = commandNr

    def brk(self):
        """Terminate executing (break from) the current command block."""
        # 'Go to' an inexistent command. The location will do the rest.
        self.location.commandNr = self.location.commands.count + 1

    def openSetParentalLevel(self, cmd):
        """Try to set parental level.

        If successful, jump to the specified command."""
        print >> sys.stderr, "Set parental level tried, implement me!"
        return TRUE


class CellNavigator(object):
    __slots__ = ('machine')

    def __init__(self, machine):
        self.machine = machine



    #
    # Command Execution
    #

    def selectButton(self, buttonNr):
        """Select the specified button in the current menu."""
        if not 0 <= buttonNr <= 36:
            raise MachineException, "Button number out of range"

        self.location.button = buttonNr
        self.updatePipeline()

    def setSystemParam8(self, value):
        """Select the button specified by the 6 most significant bits
        of the 16 value 'value'."""
        self.selectButton(value >> 10)

    def saveLocation(self, rtn=0):
        """Save the current location in the resume location.

        If 'rtn' is not zero, it specifies the cell number to return
        to when the saved state is resumed."""
        if rtn != 0:
            self.linkCell(rtn)
        self.resumeLocation = copy.copy(self.location)

    def setAngle(self, angle):
        """Set the current angle to the specified angle number."""
        if self.angle != angle:
            self.angle = angle

    def setAudio(self, audio):
        """Set the current audio stream as specified."""
        if self.audio != audio:
            self.audio = audio

    def setSubpicture(self, subpicture):
        """Set the current subpicture stream as specified."""
        if self.subpicture != subpicture:
            self.subpicture = subpicture

    def setKaraokeMode(self, mode):
        """Set the karaoke mode."""
        print >> sys.stderr, "Attempt to set karaoke mode, implement me!"


    def performCommand(self, cmd):
        global disasm

        disasm.decodeCommand(cmd, self.location.commandNr - 1)
        print >> sys.stderr, disasm.getText()
        disasm.resetText()

        try:
            self.decoder.performCommand(cmd)
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

        # Put an EOS token in the queue.
        self.queueEvent(EosEvent())

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

    def force(self):
        # A hack to handle misbehaving menus.
        self.selectButtonInteractive(1)


class VirtualMachine(object):
    """A DVD playback virtual machine implementation."""

    __slots__ = ()

    def __init__(self, info, src):
        pass


    #
    # Signal Handling
    #

    def vobuRead(self, src):
        """Invoked by the source element after reading a complete
        VOBU."""
        pass

    def vobuHeader(self, src, buffer):
        """Invoked by the source element when it finds a VOBU
        header."""
        pass
    vobuHeader = synchronized(vobuHeader)

    def flushSource(self):
        """Stop the source element on its tracks."""
        self.src.set_property('block-count', 0)


    #
    # Registers
    #

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
        """Return the object corresponding to the specified general
        purpose register."""
        assert 0 <= regNr <= 15
        return self.generalRegisters[regNr]

    def getSystemParameter(self, regNr):
        """Return the object corresponding to the specified system
        parameter."""
        assert 0 <= regNr <= 23
        return self.systemRegisters[regNr]


