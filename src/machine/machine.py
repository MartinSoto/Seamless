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

import sys
import time

import itersched
from itersched import NoOp, Call, Chain, Restart, restartPoint

import dvdread
import decode
import disassemble
import cmds


def strToIso639(strCode):
    """Encode an ISO639 country name to byte form."""
    strCode = strCode.lower()
    return ord(strCode[0]) * 0x100 + ord(strCode[1])

def iso639ToStr(iso639):
    """Decode an ISO639 country name from byte form."""
    return chr(iso639 >> 8) + chr(iso639 & 0xff)


class MachineException(Exception):
    """Base class for exceptions caused by the virtual machine."""
    pass


# A command disassembler for debugging.
disasm = disassemble.CommandDisassembler()


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


def callOperation(method):
    def wrapper(self, *args):
        yield Chain(self.wrapCallOperation(method, *args))

    return wrapper

class VirtualMachine(object):
    __slots__ = ('info',

                 'sched',

                 'audio',
                 'subpicture',
                 'angle',
                 'regionCode',
                 'prefMenuLang',
                 'prefAudio',
                 'prefSubpicture',
                 'parentalCountry',
                 'parentalLevel',
                 'aspectRatio',
                 'videoMode',

                 'currentButton',

                 'generalRegisters',
                 'systemRegisters',

                 'currentNav',
                 'buttonNav')

    def __init__(self, info):
        self.info = info

        # Current logical audio and subpicture streams and current
        # angle. The values follow the conventions of system registers
        # 1, 2, and 3, respectively.
        self.audio = 0		# Audio stream 0.
        self.subpicture = 0	# Subpicture stream 0, hidden.
        self.angle = 1

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
        # The current pipeline implementation doesn't really support
        # the letterboxed mode.
        #self.aspectRatio = dvdread.ASPECT_RATIO_4_3

        # Current video mode.
        self.videoMode = dvdread.VIDEO_MODE_NORMAL

        # Current highlighted button.
        self.currentButton = 0

        # Initialize all machine registers.
        self.generalRegisters = None
        self.systemRegisters = None
        self.initializeRegisters()

        # The navigation packets.
        self.currentNav = None
        self.buttonNav = None

        # Initialize the scheduler. Playback starts by playing the
        # first play program chain.
        self.sched = itersched.Scheduler(DiscPlayer(self). \
                                         jumpToFirstPlay())

    def __iter__(self):
        return self.sched

    def callIterator(self, itr):
        """Put 'itr' on top of this object's iterator scheduler.

        If 'itr' is a scheduler, it will be absorbed by this object's
        scheduler."""
        self.sched.call(itr)


    #
    # Navigation Packets
    #

    def setCurrentNav(self, nav):
        """Set the current navigation packet.

        The machine expects this method to be called always immediatly
        after it has yielded a `cmds.PlayVobu` operation. Following
        the `PlayVobu`, the machine will always send a single
        operation to cancel or to keep playing the VOBU, potentially
        based on the contents of the packet set here.

        This navigation packet is used strictly for navigation, i.e.,
        to determine the next position in the disc that has to be
        played. For menu highlights see the 'setButtonNav' method."""
        self.currentNav = nav

    def setButtonNav(self, buttonNav):
        """Set the current navigation packet used for menu buttons.

        This navigation packet is used to lookup menu button highlight
        positions and to determine button actions. For disc
        navigation, see the 'setCurrentNav' method.

        The reason to keep this packet separated from the current
        navigation packet is that a playback engine will normally have
        a buffer inserted between the stage that reads material from
        the disc, and the stage that displays it. The engine may want
        to use the button information in a packet only when it has
        reached the display stage."""
        oldButtonNav = self.buttonNav
        
        self.buttonNav = buttonNav

        # Check for forced activate.
        if 1 <= self.buttonNav.forcedActivate <= self.buttonNav.buttonCount:
            yield Call(self.selectButton(self.buttonNav.forcedActivate))
            yield Call(self.buttonCommand(self.getButtonObj().command))
            return

        # Check for forced select. It must be acknowledged once in a
        # single menu.
        if 1 <= self.buttonNav.forcedSelect <= self.buttonNav.buttonCount and \
           (oldButtonNav == None or \
            oldButtonNav.forcedSelect != self.buttonNav.forcedSelect):
            yield Call(self.selectButton(self.buttonNav.forcedSelect))
            return

        # Some (probably broken) DVDs enter menus without having a
        # selected button.
        if self.buttonNav.highlightStatus != dvdread.HLSTATUS_NONE and \
           not 1 <= self.currentButton <= self.buttonNav.buttonCount:
            # Select an arbitrary button.
            yield Call(self.selectButton(1))
            return

        # Update if necessary.
        if (oldButtonNav != None and \
            oldButtonNav.highlightStatus != dvdread.HLSTATUS_NONE and \
            buttonNav.highlightStatus == dvdread.HLSTATUS_NONE) or \
            buttonNav.highlightStatus == dvdread.HLSTATUS_NEW_INFO:
            yield Call(self.updateHighlight())

    def clearNavState(self):
        """Clear any navigation packets stored in the machine."""
        self.currentNav = None
        self.buttonNav = None


    #
    # Standard DVD Machine Operations
    #

    # Basic operations.
    def nop(self):
        """No operation."""
        yield NoOp

    def goto(self, commandNr):
        """Go to command 'commandNr' in the current command block."""
        yield Restart.goto(commandNr)

    def brk(self):
        """Terminate executing (break from) the current command block."""
        yield Restart.brk()

    def exit(self):
        """End execution of the machine."""
        yield Restart.exit()


    # Parental management
    def openSetParentalLevel(self, commandNr):
        """Try to set parental level.

        If successful, jump to the specified command."""
        yield Restart.openSetParentalLevel(commandNr)


    # Links.
    def linkCell(self, cellNr):
        """Jump to the specified cell in the current program chain."""
        yield Restart.linkCell(cellNr)

    def linkTopCell(self):
        """Jump to the beginning of the current cell."""
        yield Restart.linkTopCell()

    def linkNextCell(self):
        """Jump to the beginning of the next cell."""
        yield Restart.linkNextCell()

    def linkPrevCell(self):
        """Jump to the beginning of the previous cell."""
        yield Restart.linkPrevCell()

    def linkProgram(self, programNr):
        """Jump to the specified program in the current program
        chain.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        yield Restart.linkProgram(programNr)

    def linkTopProgram(self):
        """Jump to the beginning of the current program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        yield Restart.linkTopProgram()

    def linkNextProgram(self):
        """Jump to the beginning of the next program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        yield Restart.linkNextProgram()

    def linkPrevProgram(self):
        """Jump to the beginning of the previous program.

        Programs are a logical subdivision of program chains. A
        program is characterized by its start cell number."""
        yield Restart.linkPrevProgram()

    def linkProgramChain(self, programChainNr):
        """Jump to the program chain identified by 'programChainNr' in
        the current title."""
        yield Restart.linkProgramChain(programChainNr)

    def linkTopProgramChain(self):
        """Jump to the beginning of the current program chain."""
        yield Restart.linkTopProgramChain()

    def linkNextProgramChain(self):
        """Jump to the beginning of the next program chain."""
        yield Restart.linkNextProgramChain()

    def linkPrevProgramChain(self):
        """Jump to the beginning of the previous program chain."""
        yield Restart.linkPrevProgramChain()

    def linkGoUpProgramChain(self):
        """Jump to the 'up' program chain.

        The 'up' program chain is explicitly referenced from a given
        program chain."""
        yield Restart.linkGoUpProgramChain()

    def linkTailProgramChain(self):
        """Jump to the end command block of the current program chain."""
        yield Restart.linkTailProgramChain()

    def linkChapter(self, chapterNr):
        """Jump to the specified chapter in the current video title.

        Chapters are a logical subdivision of video title sets. Each
        chapter is characterized by the program chain and program
        where it starts."""
        yield Restart.linkChapter(chapterNr)


    # Button handling.
    def selectButton(self, buttonNr):
        """Select the specified button."""
        if not 0 <= buttonNr <= 36:
            raise MachineException, "Button number out of range"

        self.currentButton = buttonNr

        yield Call(self.updateHighlight())
        
    def setSystemParam8(self, value):
        """Set system parameter 8 to the specified value.

        This has the effect of selecting the button with number value
        >> 10."""
        yield Chain(self.selectButton(value >> 10))

    def buttonCommand(self, buttonCmd):
        """Execute 'buttonCmd' as a button command."""
        programChain = self.currentProgramChain()
        if programChain == None:
            return

        yield Call(CommandBlockPlayer(self). \
                   playButtonCmd(programChain.cellCommands,
                                 buttonCmd))

    # Jumps
    def jumpToTitle(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is provided with respect to the video
        manager, i.e. is global to the whole disk."""
        yield Restart.jumpToTitle(titleNr)

    def jumpToTitleInSet(self, titleNr):
        """Jump to the first chapter of the specified title.

        The title number is given with respect to the current video
        title set (i.e., the title set the current title belongs to.)"""
        yield Restart.jumpToTitleInSet(titleNr)

    def jumpToChapterInSet(self, titleNr, chapterNr):
        """Jump to the specified chapter in the specified title.

        The title number is provided with respect to the current video
        title set (i.e., the title set the current title belongs to.)"""
        yield Restart.jumpToChapterInSet(titleNr, chapterNr)

    def jumpToFirstPlay(self):
        """Jump to the first play program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in that
        disk when playback starts."""
        yield Restart.jumpToFirstPlay()

    def jumpToTitleMenu(self):
        """Jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title menu."""
        yield Restart.jumpToTitleMenu()

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
        yield Restart.jumpToMenu(titleSetNr, titleNr, menuType)

    def jumpToManagerProgramChain(self, programChainNr):
        """Jump to the specified program chain in the video
        manager.

        Program chains directly associated to the video manager are
        only for the menus."""
        yield Restart.jumpToManagerProgramChain(programChainNr)


    # Timed jump
    def setTimedJump(self, programChainNr, seconds):
        """Sets the special purpose registers (SPRMs) 10 and 9 with
        'programChainNr' and 'seconds', respectively.

        SPRM 9 will be set with a time value in seconds and the
        machine decreases its value automatically every second. When
        the value reaches 0, an automatic jump to the video manager
        program chain stored in register 10 will happen."""
        # FIXME: Implement this.
        print >> sys.stder, 'setTimeJump attempted, implement me!' 
        yield NoOp

    # Call and resume
    def wrapCallOperation(self, method, *args):
        """Wrap a call operation.

        This method provides the entry and exit code that is shared by
        all four call operations. This wrapper is activated with the
        '@callOperation' decorator."""
        # Save the necessary state.
        currentNav, buttonNav = self.currentNav, self.buttonNav

        # Perform the actual call operation.
        yield Call(method(self, *args))

        # Restore the state.
        self.currentNav, self.buttonNav = currentNav, buttonNav

        # If a program chain is playing, update the color lookup
        # table.
        programChain = self.currentProgramChain()
        if programChain != None:
            yield cmds.SetSubpictureClut(programChain.clut)

        yield Call(self.updateAspectRatio())
        yield Call(self.updateAudio())
        yield Call(self.updateSubpicture())
        yield Call(self.updateHighlight())

        rtn = args[-1]
        if rtn != 0:
            yield Restart.linkCell(rtn)

    @callOperation
    def callFirstPlay(self, rtn):
        """Save the current location and jump to the first play
        program chain.

        The first play program chain is a special program chain in the
        disk that is intended to be the first element played in the
        disk when playback starts. If 'rtn' is not zero, it specifies
        the cell number to return to when the saved state is resumed."""
        yield Call(DiscPlayer(self, True).jumpToFirstPlay())

    @callOperation
    def callTitleMenu(self, rtn):
        """Save the current location and jump to the title menu.

        The title menu is a menu allowing to select one of the
        available titles in a disk. Not all disks offer a title
        menu. If 'rtn' is not zero, it specifies the cell number to
        return to when the saved state is resumed."""
        yield Call(DiscPlayer(self, True).jumpToTitleMenu())

    @callOperation
    def callManagerProgramChain(self, programChainNr, rtn):
        """Save the current location and jump to the specified program
        chain in the video manager. If 'rtn' is not zero, it specifies
        the cell number to return to when the saved state is resumed.

        Program chains directly associated to the video manager are
        only for menus."""
        yield Call(DiscPlayer(self, True). \
                   jumpToManagerProgramChain(programChainNr))

    @callOperation
    def callMenu(self, menuType, rtn):
        """Save the current location and jump to the menu of the
        specified type in the current title. If 'rtn' is not zero, it
        specifies the cell number to return to when the saved state is
        resumed.

        The menu type is one of dvdread.MENU_TYPE_TITLE,
        dvdread.MENU_TYPE_ROOT, dvdread.MENU_TYPE_SUBPICTURE,
        dvdread.MENU_TYPE_AUDIO, dvdread.MENU_TYPE_ANGLE, and
        dvdread.MENU_TYPE_CHAPTER."""
        title = self.currentTitle()
        yield Call(DiscPlayer(self, True). \
                   jumpToMenu(title.videoTitleSet.titleSetNr,
                              title.titleNrInSet, menuType))

    def resume(self):
        """Resume playback at the previously saved location."""
        yield Restart.resume()


    # Selectable streams
    def setAngle(self, angle):
        """Set the current angle to the one specified."""
        if angle < 1:
            self.angle = 1
        elif angle > 9:
            self.angle = 9
        else:
            self.angle = angle

        yield NoOp
    
    def setAudio(self, logical):
        """Set the current logical audio stream to the one specified."""
        self.audio = logical
        yield Chain(self.updateAudio())
        
    def setSubpicture(self, logical):
        """Set the current logical subpicture stream to the one
        specified."""
        self.subpicture = logical
        yield Chain(self.updateSubpicture())

    # Karaoke control
    def setKaraokeMode(self, mode):
        """Set the karaoke mode to the specified one."""
        # FIXME: Implement this.
        yield NoOp


    #
    # Additional Playback Operations
    #

    def canPositionSeek(self):
        """Return `True` if and only if a position based seek
        operation is possible at the current time."""
        value = self.getValue('hasTimeMap')
        if value == None:
            return False
        else:
            return value

    def seekToPosition(self, timePosition):
        """Seek to the specified time position.

        A time position is specified as playback time in seconds from
        the beginning of the current program chain. In most cases, and
        depending on the quality of the time map provided by the disc,
        an error of 5 to 10 seconds can be expected while doing a time
        based jump.

        This operation will fail if no time map is available in the
        current program chain."""
        yield Restart.seekToPosition(timePosition)


    #
    # State Retrieval
    #

    def getValue(self, methodName):
        """Look down the current execution stack for a method with the
        specified name, call it and return its value."""
        for inst in self.sched.restartable():
            if hasattr(inst, methodName):
                return getattr(inst, methodName)()
        return None

    def currentTitleSet(self):
        """Return the `VideoTitleSet` object currently being played,
        or `None` if no such object is being played."""
        return self.getValue('currentTitleSet')

    def currentTitle(self):
        """Return the `VideoTitle` object currently being played, or
        `None` if no such object is being played."""
        return self.getValue('currentTitle')

    def currentLangUnit(self):
        """Return the `LangUnit` object currently being played, or
        `None` if no such object is being played."""
        return self.getValue('currentLangUnit')

    def currentProgramChain(self):
        """Return the `ProgramChain` object currently being played, or
        `None` if no such object is being played."""
        return self.getValue('currentProgramChain')

    def currentCell(self):
        """Return the `Cell` object currently being played, or
        `None` if no such object is being played."""
        return self.getValue('currentCell')

    def inMenu(self):
        """Return a true value if and only if we are playing a menu."""
        return self.getValue('inMenu')

    def currentVideoAttributes(self):
        """Return the current video attributes."""
        if self.inMenu():
            return self.getValue('currentMenuVideoAttributes')
        else:
            return self.getValue('currentVideoAttributes')

    def getCurrentTime(self):
        """Return the current playback time with respect to the start
        of the program chain."""
        cell = self.currentCell()
        if cell == None or self.buttonNav == None:
            return None

        return cell.startSeconds + \
               self.buttonNav.cellElapsedTime.seconds


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

    def getButtonObj(self):
        """Return the current dvdread.Button object."""
        if self.buttonNav == None or \
           self.buttonNav.highlightStatus == dvdread.HLSTATUS_NONE or \
           not 1 <= self.currentButton <= self.buttonNav.buttonCount:
            return None
        else:
            return self.buttonNav.getButton(self.currentButton,
                                            dvdread. \
                                            SUBPICTURE_PHYS_TYPE_WIDESCREEN)

    def currentAngle(self):
        """Return the current angle number."""
        return self.angle

    def currentAngleCount(self):
        """Return the current total number of angles available."""
        return self.currentTitle().angleCount

    #
    # Current Stream Control
    #

    def currentAudioStream(self):
        """Return the current logical audio stream (an integer between
        1 and 8)."""
        return self.audio + 1

    def setAudioStream(self, logical):
        """Set the current audio stream to `logical`.

        `logical` must be an integer between 1 and 8. If the stream
        doesn't exist in the current program chain, no change will be
        made."""
        if not 1 <= logical <= 8:
            raise MachineException, "Invalid logical stream number"

        programChain = self.currentProgramChain()
        if programChain == None or \
           programChain.getAudioPhysStream(logical) == None:
            return

        self.audio = logical - 1
        yield Call(self.updateAudio())

    def getAudioStreams(self):
        """Return the list of active audio streams in the current
        program chain.

        The return value is a list of pairs `(s, a)` where `s` is the
        stream number, and `a` are the audio attributes for the stream
        (a `dvdread.AudioAttributes` object)."""
        programChain = self.currentProgramChain()
        if programChain == None:
            return []

        titleSet = self.currentTitleSet()
        streams = []
        for logical in range(1, 9):
            if programChain.getAudioPhysStream(logical) != None:
                streams.append((logical,
                                titleSet.getAudioAttributes(logical)))

        return streams


    #
    # Pipeline Management and Events
    #

    def updateAspectRatio(self):
        """Set the aspect ratio based on the current video attributes."""
        attrs = self.currentVideoAttributes()
        if attrs == None:
            return

        if attrs.aspectRatio == dvdread.ASPECT_RATIO_4_3:
            yield cmds.SetAspectRatio(cmds.ASPECT_RATIO_4_3)
        elif attrs.aspectRatio == dvdread.ASPECT_RATIO_16_9:
            yield cmds.SetAspectRatio(cmds.ASPECT_RATIO_16_9)


    def updateAudio(self):
        """Send an audio event corresponding to the current logical
        audio stream."""
        programChain = self.currentProgramChain()
        if programChain == None or self.audio == 15:
            # We aren't playing a program chain, or the logical audio
            # track is explicitly set to none.
            physical = -1
        elif self.inMenu():
            # In the menu domain the physical audio is always 0.
            physical = 0
        else:
            # Try to find a physical stream from the information in
            # the program chain.
            try:
                physical = programChain.getAudioPhysStream(self.audio + 1)
            except IndexError:
                physical = None

            if physical == None:
                # Just pick the first existing stream.
                physical = -1
                for self.audio in range(1, 9):
                    newPhys = programChain.getAudioPhysStream(self.audio)
                    if newPhys != None:
                        physical = newPhys
                        break

        yield cmds.SetAudio(physical)

    def updateSubpicture(self):
        """Send a subpicture event corresponding to the current
        logical subpicture stream."""
        programChain = self.currentProgramChain()

        # Determine the logical stream.
        if programChain == None:
            logical = 0
            hide = False
        elif self.inMenu():
            # In the menu domain the logical subpicture is always 1.
            logical = 1
            hide = True
        elif self.subpicture & 0x3f > 31:
            # We aren't playing a program chain, or the logical
            # subpicture is explicitly set to none.
            logical = 0
            hide = False
        else:
            logical = (self.subpicture & 0x1f) + 1
            hide = (self.subpicture & 0x40) == 0

        # Retrieve the physical streams tuple, if possible.
        if logical > 0:
            streams = programChain.getSubpicturePhysStreams(logical)
        else:
            streams = None

        # Determine the physical stream.
        if streams == None:
            physical = -1
        else:
            if self.currentVideoAttributes().aspectRatio == \
                   dvdread.ASPECT_RATIO_4_3:
                physical = streams[dvdread.SUBPICTURE_PHYS_TYPE_4_3]
            else:
                if self.aspectRatio == dvdread.ASPECT_RATIO_16_9:
                    physical = streams[dvdread. \
                                       SUBPICTURE_PHYS_TYPE_WIDESCREEN]
                else:
                    physical = streams[dvdread. \
                                       SUBPICTURE_PHYS_TYPE_LETTERBOX]

        yield cmds.SetSubpicture(physical, hide)

    def updateHighlight(self):
        """Send a highlight event corresponding to the current
        highlighted area."""
        if self.buttonNav == None or \
           self.buttonNav.highlightStatus == dvdread.HLSTATUS_NONE or \
           not 1 <= self.currentButton <= self.buttonNav.buttonCount:
            # No highlight button.
            yield cmds.ResetHighlight()
        else:
            btnObj = self.buttonNav.getButton(self.currentButton,
                                              dvdread. \
                                              SUBPICTURE_PHYS_TYPE_WIDESCREEN)
            yield cmds.Highlight(btnObj.area, self.currentButton,
                                 btnObj.paletteSelected)


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
        title = self.currentTitle()
        if title != None:
            return title.titleNrInManager
        else:
            return 0

    def getSystem5(self):
        """Return the value of system register 5 (title_in_vts)."""
        title = self.currentTitle()
        if title != None:
            return title.titleNrInSet
        else:
            return 0

    def getSystem6(self):
        """Return the value of system register 6 (program_chain)."""
        programChain = self.currentProgramChain()
        if programChain != None:
            return programChain.programChainNr
        else:
            return 0

    def getSystem7(self):
        """Return the value of system register 7 (chapter)."""
        cell = self.currentCell()
        if cell != None:
            return cell.programNr
        else:
            return 0

    def getSystem8(self):
        """Return the value of system register 8 (highlighted_button)."""
        return self.currentButton << 10

    def getSystem9(self):
        """Return the value of system register 9 (navigation_timer)."""
        # FIXME: implement this.
        print >> sys.stderr, "Navigation timer checked, implement me!"
        return 0

    def getSystem10(self):
        """Return the value of system register 10
        (program_chain_for_timer)."""
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


class DiscPlayer(object):
    __slots__ = ('machine',
                 'callOp',
                 'videoManager')

    def __init__(self, machine, callOp=False):
        """Create a disc player, based on the given machine.

        'callOp' must be set to 'True' when the disc player is created
        as part of a call operation. Otherwise the resume command will
        continue playback by jumping to the first play program chain."""
        self.machine = machine
        self.callOp = callOp

        self.videoManager = self.machine.info.videoManager

    #
    # State Retrieval
    #

    # getValue based state retrieval methods in the machine must all
    # have a fallback implementation here. Otherwise it is possible to
    # get spurious values when the DVD performs a call operation.

    def currentTitleSet(self):
        return None

    def currentTitle(self):
        return None

    def currentLangUnit(self):
        return None

    def currentProgramChain(self):
        return None

    def currentCell(self):
        return None

    def inMenu(self):
        return False

    def currentMenuVideoAttributes(self):
        """Return the menu video attributes for video manager."""
        return self.videoManager.menuVideoAttributes

    #
    # Machine Operations
    #

    @restartPoint
    def jumpToFirstPlay(self):
        yield Call(ProgramChainPlayer(self.machine). \
                   playProgramChain(self.videoManager.firstPlay))

    @restartPoint
    def jumpToTitle(self, titleNr):
        title = self.videoManager.getVideoTitle(titleNr)
        yield Call(TitlePlayer(self.machine).playTitle(title))

    @restartPoint
    def jumpToTitleMenu(self):
        langUnit = self.machine.getLangUnit(self.videoManager)
        yield Call(LangUnitPlayer(self.machine). \
                   playMenuInUnit(langUnit, dvdread.MENU_TYPE_TITLE))

    @restartPoint
    def jumpToManagerProgramChain(self, programChainNr):
        langUnit = self.machine.getLangUnit(self.videoManager)
        yield Call(LangUnitPlayer(self.machine). \
                   playProgramChainInUnit(langUnit, programChainNr))

    @restartPoint
    def jumpToMenu(self, titleSetNr, titleNr, menuType):
        # Get the title set and title. Title set 0 is the video
        # manager.
        if titleSetNr == 0:
            titleSet = self.videoManager
        else:
            titleSet = self.videoManager.getVideoTitleSet(titleSetNr)

        title = titleSet.getVideoTitle(titleNr)

        yield Call(TitlePlayer(self.machine). \
                   playMenuInTitle(title, menuType))

    @restartPoint
    def resume(self):
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
        if self.callOp:
            # This object was created as the result of a call
            # operation.

            # This line propagates the exit operation down the
            # stack. How exactly, is left as an exercise to the
            # reader.
            yield Chain(i for i in [Restart.exit()])
        else:
            # Returning without doing anything is enough to do the
            # trick.
            yield NoOp


class TitlePlayer(object):
    __slots__ = ('machine',
                 'title')

    def __init__(self, machine):
        self.machine = machine

        self.title = None

    def currentTitleSet(self):
        """Return the title set currently being played."""
        return self.title.videoTitleSet

    def currentTitle(self):
        """Return the title currently being played."""
        return self.title

    def inMenu(self):
        return False

    def currentVideoAttributes(self):
        """Return the video attributes for the current title set."""
        return self.title.videoTitleSet.videoAttributes

    def currentMenuVideoAttributes(self):
        """Return the menu video attributes for the current title set."""
        return self.title.videoTitleSet.menuVideoAttributes

    @restartPoint
    def playTitle(self, title, chapterNr=1):
        """Play the specified chapter of the given video title."""
        self.title = title

        yield Chain(self.linkChapter(chapterNr))

    @restartPoint
    def playMenuInTitle(self, title, menuType):
        """Make the given video title current, and jump immediatly to
        the corresponding menu of the specified menu type.

        This operation is necessary to implement a particular DVD
        virtual machine command that selects a menu in the context of
        a particular video title."""
        self.title = title

        langUnit = self.machine.getLangUnit(self.title.videoTitleSet)
        yield Call(LangUnitPlayer(self.machine). \
                   playMenuInUnit(langUnit, menuType))

    @restartPoint
    def linkChapter(self, chapterNr):
        chapter = self.title.getChapter(chapterNr)
        yield Call(ProgramChainPlayer(self.machine). \
                   playProgramChain(chapter.cell.programChain,
                                    chapter.cell.cellNr))

    @restartPoint
    def jumpToTitleInSet(self, titleNr):
        yield Chain(self.jumpToChapterInSet(titleNr, 1))

    @restartPoint
    def jumpToChapterInSet(self, titleNr, chapterNr):
        title = self.title.videoTitleSet.getVideoTitle(titleNr)
        yield Chain(self.playTitle(title, chapterNr))

    @restartPoint
    def linkProgramChain(self, programChainNr):
        programChain = self.title.videoTitleSet. \
                       getProgramChain(programChainNr)
        yield Call(ProgramChainPlayer(self.machine). \
                   playProgramChain(programChain))


class LangUnitPlayer(object):
    __slots__ = ('machine',
                 'unit')

    def __init__(self, machine):
        self.machine = machine

        self.unit = None

    def currentLangUnit(self):
        """Return the language unit currently being played."""
        return self.unit

    def inMenu(self):
        return True

    @restartPoint
    def playMenuInUnit(self, unit, menuType):
        """Play the menu of the specified menu type in the given
        language unit."""
        self.unit = unit

        yield Call(ProgramChainPlayer(self.machine). \
                   playProgramChain(self.unit.getMenuProgramChain(menuType)))

    @restartPoint
    def playProgramChainInUnit(self, unit, programChainNr):
        """Play the specified program chain in the given language
        unit."""
        self.unit = unit

        yield Chain(self.linkProgramChain(programChainNr))

    @restartPoint
    def linkProgramChain(self, programChainNr):
        programChain = self.unit.getProgramChain(programChainNr)
        yield Call(ProgramChainPlayer(self.machine). \
                   playProgramChain(programChain))


class ProgramChainPlayer(object):
    __slots__ = ('machine',
                 'programChain',
                 'cell')

    def __init__(self, machine):
        self.machine = machine
        self.programChain = None
        self.cell = None

    def currentProgramChain(self):
        """Return the program chain currently being played.

        'None' is returned if no program chain is currently being
        played."""
        return self.programChain

    def hasTimeMap(self):
        """Return `True` if and only if the current program chain
        provides a time map.

        A time map associates time positions (specified as playback
        time from the beginning of the program chain) with VOBUs in
        the program chain. It can be used to jump to a particular time
        position. Normally, time maps have low accuracy. An error of 5
        to 10 seconds is to be expected while locating a position."""
        return self.programChain != None and \
               self.programChain.hasTimeMap

    @restartPoint
    def playProgramChain(self, programChain, cellNr=1):
        """Play the specified program chain.

        'cellNr' specifies the start cell."""
        self.programChain = programChain
        self.cell = None

        # Update the color lookup table.
        yield cmds.SetSubpictureClut(self.programChain.clut)

        # Update the aspect ratio.
        yield Call(self.machine.updateAspectRatio())

        # Update the audio and subpicture streams.
        yield Call(self.machine.updateAudio())
        yield Call(self.machine.updateSubpicture())

        if cellNr == 1:
            # Play the 'pre' commands.
            yield Call(CommandBlockPlayer(self.machine). \
                       playBlock(self.programChain.preCommands))

        # Go to the specified cell.
        yield Chain(self.linkCell(cellNr))

    @restartPoint
    def linkCell(self, cellNr, sectorNr=None):
        """Link to the specified cell.

        If a sector number is specified, link to that sector in the
        cell."""
        # Some DVDs use cell numbers out of range.
        if 1 <= cellNr <= self.programChain.cellCount:
            self.cell = self.programChain.getCell(cellNr)

            if self.machine.angle > 1 and \
               self.cell.blockMode == dvdread.CELL_BLOCK_MODE_ANGLE_FIRST:
                # We are at the beginning of an angle group. Jump to
                # the right cell according to the angle.
                yield Chain(self.linkCell(cellNr +
                                          self.machine.angle - 1))

            # We are moving to a new location. Clear the old,
            # navigation packets stored in the machine.
            self.machine.clearNavState()

            # Play the cell.
            yield Call(CellPlayer(self.machine).playCell(self.cell,
                                                         sectorNr))

            # Play the corresponding cell commands.
            if self.cell.commandNr != 0:
                yield Call(CommandBlockPlayer(self.machine). \
                           playBlock(self.programChain.cellCommands,
                                     self.cell.commandNr))

            if self.cell.blockMode == \
               dvdread.CELL_BLOCK_MODE_ANGLE_FIRST or \
               self.cell.blockMode == \
               dvdread.CELL_BLOCK_MODE_ANGLE_MIDDLE:
                # We just finished playing a cell in an angle
                # group. Skip to the end.
                cellNr += 1
                nextMode = self.programChain.getCell(cellNr).blockMode
                while nextMode != dvdread.CELL_BLOCK_MODE_ANGLE_LAST:
                    cellNr += 1
                    nextMode = self.programChain.getCell(cellNr).blockMode

            # Progress to the next cell in sequence.
            cellNr += 1

        if cellNr > self.programChain.cellCount:
            # No more cells. Play the "tail".
            yield Chain(self.linkTailProgramChain())
        else:
            yield Chain(self.linkCell(cellNr))

    @restartPoint
    def linkTopCell(self):
        yield Chain(self.linkCell(self.cell.cellNr))

    @restartPoint
    def linkNextCell(self):
        yield Chain(self.linkCell(self.cell.cellNr + 1))

    @restartPoint
    def linkPrevCell(self):
        yield Chain(self.linkCell(self.cell.cellNr - 1))

    @restartPoint
    def linkProgram(self, programNr):
        yield Chain(self.linkCell(self.programChain. \
                                  getProgramCell(programNr).cellNr))

    @restartPoint
    def linkTopProgram(self):
        programNr = self.cell.programNr
        yield Chain(self.linkProgram(programNr))

    @restartPoint
    def linkNextProgram(self):
        programNr = self.cell.programNr
        yield Chain(self.linkProgram(programNr + 1))

    @restartPoint
    def linkPrevProgram(self):
        programNr = self.cell.programNr
        yield Chain(self.linkProgram(programNr - 1))

    @restartPoint
    def linkTopProgramChain(self):
        yield Chain(self.playProgramChain(self.programChain))

    @restartPoint
    def linkNextProgramChain(self):
        yield Chain(self.playProgramChain(self.programChain.nextProgramChain))

    @restartPoint
    def linkPrevProgramChain(self):
        yield Chain(self.playProgramChain(self.programChain.prevProgramChain))

    @restartPoint
    def linkGoUpProgramChain(self):
        yield Chain(self.playProgramChain(self.programChain.goUpProgramChain))

    @restartPoint
    def linkTailProgramChain(self):
        self.cell = None

        # Play the "post" commands.
        yield Call(CommandBlockPlayer(self.machine). \
                   playBlock(self.programChain.postCommands))

        # If there's a next program chain, link to it.
        next = self.programChain.nextProgramChain
        if next != None:
            yield Chain(self.playProgramChain(next))

    @restartPoint
    def seekToPosition(self, timePosition):
        assert self.hasTimeMap()

        sectorNr = self.programChain.getSectorFromTime(timePosition)
        cell = self.programChain.getCellFromSector(sectorNr)
        yield Chain(self.linkCell(cell.cellNr, sectorNr=sectorNr))


class CommandBlockPlayer(object):
    __slots__ = ('machine',
                 'decoder',
                 'commands',
                 'commandNr')

    def __init__(self, machine):
        self.machine = machine

        self.decoder = decode.CommandDecoder(machine)

        self.commands = None
        self.commandNr = 0

    @restartPoint
    def playBlock(self, commands, commandNr=1):
        self.commands = commands
        yield Chain(self.goto(commandNr))

    @restartPoint
    def playButtonCmd(self, cellCommands, buttonCmd):
        """Play the specified button command.

        The command will use the cell commands block as context."""
        self.commands = cellCommands

        #print 'Button command:'
        #print disassemble.disassemble(buttonCmd)
        yield Call(self.decoder.performCommand(buttonCmd))

    @restartPoint
    def goto(self, commandNr):
        assert commandNr > 0

        self.commandNr = commandNr

        while self.commandNr <= self.commands.count:
            # Actually perform the command.
            #print disassemble.disassemble(self.commands.get(self.commandNr),
            #                              pos=self.commandNr)
            yield Call(self.decoder.performCommand( \
                self.commands.get(self.commandNr)))

            self.commandNr += 1

    @restartPoint
    def brk(self):
        # Just doing nothing should do the trick :-)
        yield NoOp

    @restartPoint
    def openSetParentalLevel(self, commandNr):
        # FIXME: implement this.
        print "Attempt to set parental level, implement me!"

        # For the moment, just jump inconditionally.
        yield Chain(self.goto(commandNr))


class CellPlayer(object):
    """A player for DVD cells."""

    __slots__ = ('machine',
                 'cell',	# Cell currently being played.
                 'domain',	# Playback domain this cell belongs to.
                 'titleSetNr',	# DVD video title set number the cell is in.
                 'sectorNr')	# Last sector played.

    def currentCell(self):
        """Return the cell currently being played.

        'None' is returned if no cell is currently being played."""
        return self.cell

    def __init__(self, machine):
        self.machine = machine
        self.cell = None
        self.domain = None
        self.titleSetNr = None
        self.sectorNr = None

    @restartPoint
    def playCell(self, cell, sectorNr=None):
        """Play the specified cell.

        If a sector number is specified, playback of the cell will
        start there."""
        self.cell = cell

        # Find the playback domain for the cell.
        if self.machine.inMenu():
            self.domain = dvdread.DOMAIN_MENU
        else:
            self.domain = dvdread.DOMAIN_TITLE

        # Find the DVD title set number for the cell.
        titleSet = self.machine.currentTitleSet()
        if titleSet != None:
            self.titleSetNr = titleSet.titleSetNr
        else:
            self.titleSetNr = 0

        if sectorNr == None:
            # Just play the first VOBU in the cell.
            yield Chain(self.playFromVobu(cell.firstSector))
        else:
            yield Chain(self.seekToSector(sectorNr))

    def getNextPointer(self, nav, forceAngleJump=False):
        """Find the pointer to the next VOBU based on the current
        state and on the provided nav packet."""
        if self.cell.blockMode != dvdread.CELL_BLOCK_MODE_NORMAL:
            angle = self.machine.angle

            nextPtr = 0
            if nav.interleaved and (nav.unitEnd or forceAngleJump):
                # Seamless angle. We are at the end of an interleaved
                # unit or we are forced to jump to the next
                # interleaved unit (normal after a seek).
                nextPtr = nav.getSeamlessNextInterleavedUnit(angle)
            else:
                nextPtr = nav.getNonSeamlessNextVobu(angle)

            if nextPtr == 0:
                return nav.nextVobu
            else:
                return nextPtr
        else:
            return nav.nextVobu

    @restartPoint
    def seekToSector(self, sectorNr):
        """Seek to the specified sector."""
        self.sectorNr = sectorNr

        yield cmds.PlayVobu(self.domain, self.titleSetNr, self.sectorNr)
        nav = self.machine.currentNav

        if self.cell.blockMode != dvdread.CELL_BLOCK_MODE_NORMAL:
            # Don't play the first VOBU but jump to the right angle
            # first.
            yield cmds.CancelVobu()
        else:
            yield cmds.AcceptVobu()

        nextPtr = self.getNextPointer(nav, True)
        if nextPtr != None:
            yield Chain(self.playFromVobu(sectorNr + nextPtr))

    @restartPoint
    def playFromVobu(self, sectorNr):
        """Play the VOBU at the specified sector number."""
        self.sectorNr = sectorNr

        # Play until the end of the cell.
        nav = None
        while True:
            yield cmds.PlayVobu(self.domain, self.titleSetNr, self.sectorNr)

            # At this point, a new nav packet must be there. If this
            # is not the case, we have a serious problem.
            assert nav != self.machine.currentNav

            # Accept playing this VOBU.
            yield cmds.AcceptVobu()

            nav = self.machine.currentNav

            nextPtr = self.getNextPointer(nav)
            if nextPtr != None:
                # Progress to the next VOBU.
                self.sectorNr += nextPtr
            else:
                # We reached the end of the cell.
                break

        if self.cell.stillTime > 0:
            # We have a still frame.

            if self.cell.stillTime == 0xff:
                # Unlimited wait time. Loop "infinitely" until a
                # restart operation takes this method out of the
                # stack.
                while True:
                    yield cmds.Pause()
            else:
                # Wait the specified number of seconds.
                endTime = time.time() + self.cell.stillTime
                while time.time() < endTime:
                    yield cmds.Pause()
