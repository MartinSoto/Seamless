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

import gst

import dvdread
import machine
import manager
from manager import interactiveOp
import pipeline

from itersched import NoOp, Call
from sig import SignalHolder, signal


class DVDPlayer(SignalHolder):
    """Main interface to interactively control the DVD playback system
    and query its state."""

    __slots__ = ('info',
                 'machine',
                 'pipeline',
                 'manager')

    def __init__(self, options):
        # Create an info object for the DVD.
        self.info = dvdread.DVDInfo(options.location)

        # Create the machine, pipeline and manager objects. All
        # objects will be set into motion as soon as the source object
        # in the pipeline is activated.
        self.machine = machine.VirtualMachine(self.info)
        self.pipeline = pipeline.Pipeline(options)
        self.manager = manager.Manager(self.machine, self.pipeline)

        # Set the region.
        self.setRegion(int(options.region))

    def getDVDInfo(self):
        return self.info

    def getVideoSink(self):
        return self.pipeline.getVideoSink()


    #
    # Player Configuration
    #

    def setRegion(self, region):
        """Set the player's region."""
        self.machine.setRegion(region)

    def getRegion(self):
        """Return the player's region code."""
        return self.machine.getRegion()
        

    #
    # Basic Playback Control
    #

    def start(self):
        self.pipeline.set_state(gst.STATE_PLAYING)

    def pause(self):
        """Toggle between paused and playing."""
        (status, state, pending) = self.pipeline.get_state()

        if state == gst.STATE_PLAYING:
            self.pipeline.set_state(gst.STATE_PAUSED)
        elif state == gst.STATE_PAUSED:
            self.pipeline.set_state(gst.STATE_PLAYING)

    @interactiveOp
    def stopMachine(self):
        yield Call(self.machine.exit())

    def stop(self):
        self.stopMachine()

        # Wait for the pipeline to actually reach the paused state.
        maxIter = 40
        while maxIter > 0 and \
                  self.pipeline.get_state() == gst.STATE_PLAYING:
            time.sleep(0.1)
            maxIter -= 1

        # Shutdown the pipeline and confirm the state.
        self.pipeline.set_state(gst.STATE_NULL)
        self.pipeline.get_state()


    #
    # Program Navigation
    #

    @interactiveOp
    def prevProgram(self):
        cell = self.machine.currentCell()
        if cell == None:
            return

        newProgram = cell.programNr - 1
        if newProgram == 0:
            # Restart from the beginning.
            newProgram = 1

        yield Call(self.machine.linkProgram(newProgram))

    @interactiveOp
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
        return self.machine.getCurrentTime()

    def canPositionSeek(self):
        return self.machine.canPositionSeek()

    @interactiveOp
    def seekToPosition(self, timePostion):
        yield Call(self.machine.seekToPosition(timePosition))

    @interactiveOp
    def seekToPositionRelative(self, seconds):
        currentTime = self.machine.getCurrentTime()
        if currentTime != None:
            yield Call(self.machine. \
                       seekToPosition(currentTime + seconds))

    def backward10(self):
        if self.canPositionSeek():
            self.seekToPositionRelative(-10)

    def forward10(self):
        if self.canPositionSeek():
            self.seekToPositionRelative(10)


    #
    # Stream Control
    #

    @interactiveOp
    def setAudioStream(self, logical):
        yield Call(self.machine.setAudioStream(logical))

    def getAudioStreams(self):
        return self.machine.getAudioStreams()

    @interactiveOp
    def nextAudioStream(self):
        streamNumbers = [s for (s, a) in self.machine.getAudioStreams()]
        if streamNumbers == []:
            return

        try:
            pos = streamNumbers.index(self.machine.currentAudioStream())
        except ValueError:
            return

        stream = streamNumbers[(pos + 1) % len(streamNumbers)]
        yield Call(self.machine.setAudioStream(stream))


    #
    # Angle Selection
    #

    @interactiveOp
    def nextAngle(self):
        """Switch to next angle."""
        yield Call(self.machine. \
                   setAngle((self.machine.currentAngle() % \
                             self.machine.currentAngleCount()) + 1))


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

    @interactiveOp
    def up(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.up
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @interactiveOp
    def down(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.down
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @interactiveOp
    def left(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.left
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @interactiveOp
    def right(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        nextBtn = btnObj.right
        if nextBtn != 0:
            yield Call(self.selectButtonInteractive(nextBtn))

    @interactiveOp
    def confirm(self):
        btnObj = self.machine.getButtonObj()
        if btnObj == None:
            return

        yield Call(self.machine.buttonCommand(btnObj.command))

    @interactiveOp
    def menu(self):
        if self.machine.inMenu():
            return

        yield Call(self.machine.callMenu(dvdread.MENU_TYPE_ROOT, 0))
