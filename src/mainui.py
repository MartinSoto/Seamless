# Seamless DVD Player
# Copyright (C) 2004-2006 Martin Soto <martinsoto@users.sourceforge.net>
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

import os
import sys
import traceback

import gst

import gtk

import debug
import tasklet
import player
from baseui import UIManager, ActionGroup, action, toggleAction
import mainwindow

# "Plugins"
import lirc
import xscreensaver


class MainUserInterface(UIManager):
    """The class responsible for creating all widgets and implementing
    the main actions associated to the Seamless user interface."""

    __slots__ = ('player',
                 'options',
                 
                 'window',

                 'lirc',
                 'xscreensaver')

    def __init__(self, player, options):
        super(MainUserInterface, self).__init__()

        self.player = player
        self.options = options

        # Create the main window.
        self.window = mainwindow.MainWindow(self)
        self.window.connect('destroy', lambda widget: self.shutDown())
        self.window.fullScreen(options.fullScreen)
        self.window.show()

        # Initialize all 'plugins'.
        # FIXME: A decent framework for extensions is necessary here.
        if self.options.lirc:
            self.lirc = lirc.LIRC(self)
        self.xscreensaver = xscreensaver.XScreensaver(self)

    def getPlayer(self):
        return self.player

    def getOptions(self):
        return self.options

    @tasklet.task
    def shutdown(self):
        self.window.hide()

        # Stop the player, and wait for actual termination.
        self.player.stop()
        yield tasklet.WaitForSignal(self.player, 'stopped')
        tasklet.get_event()

        # Stop control plugins.
        # FIXME: A decent framework for extensions is necessary here.
        if self.options.lirc:
            self.lirc.close()
        self.xscreensaver.close()

        gtk.main_quit()


    class alwaysAvailable(ActionGroup):
        """Always available operations."""

        @action(stockId=gtk.STOCK_GO_UP)
        def up(ui, action):
            ui.player.up()

        @action(stockId=gtk.STOCK_GO_DOWN)
        def down(ui, action):
            ui.player.down()

        @action(stockId=gtk.STOCK_GO_BACK)
        def left(ui, action):
            ui.player.left()

        @action(stockId=gtk.STOCK_GO_FORWARD)
        def right(ui, action):
            ui.player.right()

        @action(stockId=gtk.STOCK_OK)
        def confirm(ui, action):
            ui.player.confirm()

        @action(stockId=gtk.STOCK_HOME, label=_('Menu'), accel='m',
                tooltip=_('Go to the DVD menu'))
        def menu(ui, action):
            ui.player.menu()


        @toggleAction(stockId=gtk.STOCK_MEDIA_PAUSE, accel='p',
                tooltip=_('Pause playback'))
        def pause(ui, action):
            ui.player.pause(action.get_active())

        @action(stockId=gtk.STOCK_MEDIA_PREVIOUS, accel='Page_Up',
                tooltip=_('Jump to previous chapter'))
        def prevProgram(ui, action):
            ui.player.prevProgram()

        @action(stockId=gtk.STOCK_MEDIA_NEXT, accel='Page_Down',
                tooltip=_('Jump to next chapter'))
        def nextProgram(ui, action):
            ui.player.nextProgram()

        @action(stockId=gtk.STOCK_MEDIA_REWIND, accel='<Shift>Left',
                tooltip=_('Jump 10 seconds backward'))
        def backward10(ui, action):
            ui.player.backward10()

        @action(stockId=gtk.STOCK_MEDIA_FORWARD, accel='<Shift>Right',
                tooltip=_('Jump 10 seconds forward'))
        def forward10(ui, action):
            ui.player.forward10()


        @toggleAction(stockId=gtk.STOCK_FULLSCREEN)
        def fullScreen(ui, action):
            ui.window.fullScreen(action.get_active())


        @action(label=_("Next Audio"), accel='F2',
                tooltip=_('Select next audio track'))
        def nextAudioStream(ui, action):
            ui.player.nextAudioStream()

        @action(label=_("Next Angle"), accel='F3',
                tooltip=_('Select next angle'))
        def nextAngle(ui, action):
            ui.player.nextAngle()


        @action(stockId=gtk.STOCK_QUIT, accel='<Ctrl>Q',
                tooltip=_(''))
        def quit(ui, action):
            ui.shutdown()


        @action(label=_("Debug Console"), accel='<Ctrl>F12')
        def debugConsoleAsync(ui, action):
            debug.debugConsoleAsync(ui.player)

