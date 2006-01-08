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
import player
from baseui import UIManager, ActionGroup, action
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

        # Initialize all 'plugins'.
        # FIXME: A decent framework for extensions is necessary here.
        if self.options.lirc:
            self.lirc = lirc.LIRC(self)
        self.xscreensaver = xscreensaver.XScreensaver(self)

    def getPlayer(self):
        return self.player

    def getOptions(self):
        return self.options

    def shutDown(self):
        self.window.hide()

        self.player.stop()

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

        @action(stockId=gtk.STOCK_HOME)
        def menu(ui, action):
            ui.player.menu()


        @action(stockId=gtk.STOCK_MEDIA_PAUSE)
        def pause(ui, action):
            ui.player.pause()

        @action(stockId=gtk.STOCK_MEDIA_PREVIOUS)
        def prevProgram(ui, action):
            ui.player.prevProgram()

        @action(stockId=gtk.STOCK_MEDIA_NEXT)
        def nextProgram(ui, action):
            ui.player.nextProgram()

        @action(stockId=gtk.STOCK_MEDIA_REWIND)
        def backward10(ui, action):
            ui.player.backward10()

        @action(stockId=gtk.STOCK_MEDIA_FORWARD)
        def forward10(ui, action):
            ui.player.forward10()


        @action(label=_("Next Audio"))
        def nextAudioStream(ui, action):
            ui.player.nextAudioStream()

        @action(label=_("Next Angle"))
        def nextAngle(ui, action):
            ui.player.nextAngle()


        @action(stockId=gtk.STOCK_QUIT)
        def quit(ui, action):
            ui.shutDown()


        @action(label=_("Debug Console"))
        def debugConsoleAsync(ui, action):
            debug.debugConsoleAsync(ui.player)

