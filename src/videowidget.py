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

import threading

import gobject
import gtk

import gst
import gst.interfaces


class VideoWidget(gtk.EventBox):
    __gsignals__ = {
        'ready' : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   ())
        }

    def __init__(self):
        self.__gobject_init__()

        # A lock to protect accesses to the display window.
        self.xlock = threading.RLock()

        self.set_visible_window(False)
        self.set_above_child(True)
        self.set_events(gtk.gdk.POINTER_MOTION_MASK)
        self.connect('size-allocate', self.sizeAllocateCb)
        self.connect('motion-notify-event', self.motionCb)
        self.connect('destroy', self.destroyCb)

        self.background = gtk.DrawingArea()
        self.background.modify_bg(gtk.STATE_NORMAL,
                                  gtk.gdk.color_parse('black'))
        self.add(self.background)
        self.background.show()
        self.background.connect('realize', self.backgroundRealizeCb)

        self.videoWin = None
        self.videoWinExposed = False

        self.imageSink = None

        self.pixelAspect = 1.0
        self.desiredAspect = 4.0 / 3
        self.presetAspect = None

        self.cursorTimeout = None
        self.invisibleCursor = None


    def setImageSink(self, imageSink):
        assert isinstance(imageSink, gst.interfaces.XOverlay)
        self.imageSink = imageSink
        self.imageSink.connect('desired-size-changed',
                               self.desiredSizeChanged)

    def getImageSink(self):
        return self.imageSink

    def setPixelAspect(self, pixelAspect):
        self.pixelAspect = pixelAspect

    def presetAspectRatio(self, presetAspect):
        """Preset an aspect ratio to use from the next aspect ratio
        change on.

        The preset value will supersede any values set by the stream,
        but will be activated only when the stream changes aspect
        ratios. Passing a `None` value will deactivate the preset."""
        self.presetAspect = presetAspect


    #
    # Internal Operations
    #

    def resizeVideo(self):
        if self.window == None:
            return

        allocation = self.get_allocation()
        widgetAspect = float(allocation.width) / allocation.height

        desiredAspect = self.desiredAspect / self.pixelAspect

        if widgetAspect >= desiredAspect:
            width = allocation.height * desiredAspect
            height = allocation.height
            x = (allocation.width - width) / 2
            y = 0
        else:
            width = allocation.width
            height = allocation.width / desiredAspect
            x = 0
            y = (allocation.height - height) / 2

        if self.videoWin:
            self.xlock.acquire()
            self.videoWin.move_resize(int(x), int(y), int(width), int(height))
            self.xlock.release()

    def getInvisibleCursor(self):
        if self.invisibleCursor:
           return self.invisibleCursor

        display = self.get_display()
        if display == None:
            return None

        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 1, 1)
        pixbuf.fill(0x00000000)
        self.invisibleCursor = gtk.gdk.Cursor(display, pixbuf, 0, 0);
        return self.invisibleCursor


    #
    # Signal Handlers
    #

    def desiredSizeChanged(self, imageSink, width, height):
        if self.presetAspect:
            self.desiredAspect = self.presetAspect
        else:
            self.desiredAspect = float(width) / height
        self.resizeVideo()


    #
    # Callbacks
    #

    def sizeAllocateCb(self, widget, allocation):
        self.resizeVideo()

    def motionCb(self, widget, event):
        if self.cursorTimeout == None:
            self.window.set_cursor(None)
        else:
            gobject.source_remove(self.cursorTimeout)
        self.cursorTimeout = gobject.timeout_add(5000, self.hidePointer)

    def hidePointer(self):
        self.window.set_cursor(self.getInvisibleCursor())
        self.cursorTimeout = None
        return False

    def destroyCb(self, da):
        self.imageSink.set_xwindow_id(0L)

    def backgroundRealizeCb(self, widget):
        # Create the video window.
        self.videoWin = gtk.gdk.Window(
            self.background.window,
            1, 1,
            gtk.gdk.WINDOW_CHILD,
            gtk.gdk.EXPOSURE_MASK,
            gtk.gdk.INPUT_OUTPUT,
            "",
            0, 0)
        self.videoWin.add_filter(self.videoEventFilter)

        self.videoWin.show()

    def videoEventFilter(self, event):
        # FIXME: Check for expose event here. Cannot be done now
        # because pygtk seems to have a bug and only reports "NOTHING"
        # events.
        self.xlock.acquire()

        if not self.videoWinExposed:
            # We are ready to display video. The 'ready' signal could
            # actually set up the image sink.
            self.emit('ready')

            if self.videoWin:
                self.imageSink.set_xwindow_id(self.videoWin.xid)
                self.videoWinExposed = True

            # Hide the pointer now.
            self.hidePointer()

        self.imageSink.expose()

        self.xlock.release()

        return gtk.gdk.FILTER_CONTINUE
