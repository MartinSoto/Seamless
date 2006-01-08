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
import mainwindow

# "Plugins"
import lirc
import xscreensaver


class MainUserInterface(object):
    __slots__ = ('player',
                 'options',
                 
                 'window',

                 'lirc',
                 'xscreensaver')

    def __init__(self, player, options):
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
