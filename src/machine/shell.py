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

import machine
import pipeline
import pipelinecmds as cmds

from itersched import NoOp, Call

import dvdread


def entryPoint(method):
    """Create a machine entry point that will be executed instantly
    when invoked.

    'method' will be wrapped to be run using the 'runEntryPoint'
    method in the pipeline object."""
    def wrapper(self, *args, **keywords):
        self.pipeline.runEntryPoint(method(self, *args, **keywords))

    return wrapper

class MachineShell(object):
    """External interface to interactively control the DVD virtual
    machine and query its state."""

    __slots__ = ('info',
                 'src',
                 'machine',
                 'pipeline')

    def __init__(self, info, src):
        self.info = info
        self.src = src

        # Create the machine and pipeline objects. Both objects will
        # be sent into motion as soon as the src object is activated.
        self.machine = machine.VirtualMachine(info)
        self.pipeline = pipeline.Pipeline(src, self.machine)

    @entryPoint
    def stop(self):
        yield Call(self.machine.exit())

    @entryPoint
    def prevProgram(self):
        cell = self.machine.currentCell()
        if cell == None:
            return

        newProgram = cell.programNr - 1
        if newProgram == 0:
            # Restart from the beginning.
            newProgram = 1

        yield Call(self.machine.linkProgram(newProgram))

    @entryPoint
    def nextProgram(self):
        cell = self.machine.currentCell()
        if cell == None:
            return

        newProgram = cell.programNr + 1
        if newProgram > cell.programChain.programCount:
            yield Call(self.machine.linkTailProgramChain())
        else:
            yield Call(self.machine.linkProgram(newProgram))


    #
    # Time Based Navigation
    #

    def getCurrentTime(self):
        pass
    currentTime = property(getCurrentTime)

    def getCanTimeJump(self):
        return False
    canTimeJump = property(getCanTimeJump)

    @entryPoint
    def timeJump(self, seconds):
        yield NoOp

    @entryPoint
    def timeJumpRelative(self, seconds):
        yield NoOp


    #
    # Stream Control
    #

    def getAudioStream(self):
        return None

    def setAudioStream(self, logical):
        pass
    audioStream = property(getAudioStream, setAudioStream)

    def getAudioStreams(self):
        return None


    #
    # Button Navigation
    #

    def selectButtonInteractive(self, buttonNr):
        """Select a button in interactive mode."""
        yield Call(self.machine.selectButton(buttonNr))

        btnObj = self.machine.getButtonObj()
        if btnObj != None and btnObj.autoAction:
            # Automatically execute the button's action.
            yield Call(self.machine.buttonCommand(btnObj.command))

    @entryPoint
    def up(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.up
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @entryPoint
    def down(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.down
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @entryPoint
    def left(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.left
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @entryPoint
    def right(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.right
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @entryPoint
    def confirm(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        yield Call(self.machine.buttonCommand(btnObj.command))

    @entryPoint
    def menu(self):
        programChain = self.machine.currentProgramChain()
        if programChain == None or \
               isinstance(programChain.container, dvdread.LangUnit):
            return

        yield Call(self.machine.callMenu(dvdread.MENU_TYPE_ROOT, 0))

    @entryPoint
    def rtn(self):
        yield NoOp

    @entryPoint
    def force(self):
        yield NoOp

