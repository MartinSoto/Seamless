# Seamless DVD Player
# Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
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
import time
import traceback

import gobject
try:
    gobject.threads_init()
except:
    print "WARNING: gobject doesn't have threads_init, no threadsafety"

import gst

import pygtk
pygtk.require('2.0')
import gtk

import dvdplayer
import videowidget

# "Plugins"
import lirc
import xscreensaver


class MainUserInterface(object):
    def __init__(self, player, options):
        self.player = player
        self.options = options

        # Create the main window.
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title('DVD Player')
        self.window.set_border_width(0)
        self.window.set_property('can-focus', True)

        self.window.connect('key-press-event', self.mainKeyPress)
        self.window.connect('delete_event', self.mainDeleteEvent)
        self.window.connect('destroy', self.mainDestroy)

        self.video = videowidget.VideoWidget()
        self.window.add(self.video)
        
        self.video.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.video.connect('ready', self.videoReady)
        self.video.connect('button-press-event', self.videoButtonPress)

        # Give the window a decent minimum size.
        self.window.set_size_request(480, 360)

        # Set the initial dimensions of the window to 75% of the screen.
        (rootWidth, rootHeight) = \
                    self.window.get_root_window().get_geometry()[2:4]
        self.window.set_default_size(int(rootWidth * 0.75),
                                     int(rootHeight * 0.75))

        # Set the proper full screen mode.
        self.fullScreen = self.options.fullScreen
        self.performFullScreen()

        # Show the actual windows.
        self.video.show()
        self.window.show()

        # Initialize all 'plugins'.
        if self.options.lirc:
            self.lirc = lirc.LIRC(self)
        self.xscreensaver = xscreensaver.XScreensaver(self)

    def getPlayer(self):
        return self.player

    def shutDown(self):
        # Stop control plugins.
        if self.options.lirc:
            self.lirc.close()
        self.xscreensaver.close()

        self.player.stop()

        gtk.main_quit()

    def isFullScreen(self):
        return self.fullScreen

    def performFullScreen(self):
        if self.fullScreen:
            self.window.fullscreen()
            self.window.set_keep_above(1)
            self.video.grab_focus()
        else:
            self.window.unfullscreen()
            self.window.set_keep_above(0)

    def toggleFullScreen(self):
        self.fullScreen = not self.fullScreen
        self.performFullScreen()


    #
    # Callbacks
    #

    def mainKeyPress(self, widget, event):
        keyName = gtk.gdk.keyval_name(event.keyval)

        if keyName == 'Up':
            self.player.up()
        elif keyName == 'Down':
            self.player.down()
        elif event.state == 0 and keyName == 'Left':
            self.player.left()
        elif event.state == 0 and keyName == 'Right':
            self.player.right()
        elif keyName == 'Return':
            self.player.confirm()
        elif keyName == 'Page_Up':
            self.player.prevProgram()
        elif keyName == 'Page_Down':
            self.player.nextProgram()
        elif event.state == gtk.gdk.SHIFT_MASK and keyName == 'Left':
            self.player.backward10()
        elif event.state == gtk.gdk.SHIFT_MASK and keyName == 'Right':
            self.player.forward10()
        elif keyName == 'Escape':
            self.player.menu()
        elif keyName == 'F2':
            self.player.nextAudioStream()

        return False

    def mainDeleteEvent(self, widget, event):
        return False

    def mainDestroy(self, widget):
        self.shutDown()

    def videoReady(self, widget):
        # Setup and start the player.
        self.video.setImageSink(self.player.getVideoSink())
        self.player.start()

    def videoButtonPress(self, widget, event):
        self.toggleFullScreen()
