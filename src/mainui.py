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


class MainUserInterface:
    def __init__(self, player, fullScreen=False):
        self.player = player
        self.fullScreen = fullScreen

        # Create and display the window.
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title('DVD Player')
        self.window.set_border_width(0)
        self.window.set_property('can-focus', True)
        self.performFullScreen()

        self.window.connect("realize", self.mainRealize)
        self.window.connect("key-press-event", self.mainKeyPress)
        self.window.connect("delete_event", self.mainDeleteEvent)
        self.window.connect("destroy", self.mainDestroy)

        self.video = videowidget.VideoWidget()
        self.window.add(self.video)
        self.video.set_size_request(400, 400)
        
        self.video.setEventMask(gtk.gdk.BUTTON_PRESS_MASK)
        self.video.connect('button-press-event', self.videoButtonPress)
        
        self.video.show()
        self.window.show()

        # Initialize all 'plugins'.
        self.lirc = lirc.LIRC(self)
        self.xscreensaver = xscreensaver.XScreensaver(self)

    def getPlayer(self):
        return self.player

    def shutDown(self):
        # Stop control plugins.
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

    def mainRealize(self, widget):
        # Setup and start the player.
        self.video.setImageSink(self.player.getVideoSink())
        self.player.start()

    def mainKeyPress(self, widget, event):
        keyName = gtk.gdk.keyval_name(event.keyval)

        if keyName == "Up":
            self.player.up()
        elif keyName == "Down":
            self.player.down()
        elif event.state == 0 and keyName == "Left":
            self.player.left()
        elif event.state == 0 and keyName == "Right":
            self.player.right()
        elif keyName == "Return":
            self.player.confirm()
        elif keyName == "Page_Up":
            self.player.prevProgram()
        elif keyName == "Page_Down":
            self.player.nextProgram()
        elif event.state == gtk.gdk.SHIFT_MASK and keyName == "Left":
            self.player.backward10()
        elif event.state == gtk.gdk.SHIFT_MASK and keyName == "Right":
            self.player.forward10()
        elif keyName == "Escape":
            self.player.menu()
        elif keyName == "F2":
            self.player.nextAudioStream()

        return False

    def mainDeleteEvent(self, widget, event):
        return False

    def mainDestroy(self, widget):
        self.shutDown()

    def videoButtonPress(self, widget, event):
        self.toggleFullScreen()
