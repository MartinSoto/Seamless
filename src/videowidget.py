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

import threading

import gobject
import gtk

import gst
import gst.interfaces


class VideoWidget(gtk.EventBox):
    __slots__ = ('background',
                 'videoWin',
                 'overlay',
                 'pipeline',
                 'cursorTimeout'
                 'invisibleCursor')

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

        self.overlay = None

        self.cursorTimeout = None
        self.invisibleCursor = None


    def setOverlay(self, overlay):
        assert isinstance(overlay, gst.interfaces.XOverlay)
        self.overlay = overlay

        # Find the pipeline object containing the image sink. It must
        # support installing synchronous message handlers, but we
        # don't check for it.
        self.pipeline = overlay
        while not isinstance(self.pipeline, gst.Pipeline):
            self.pipeline = self.pipeline.get_parent()

        # Install a handler for the prepare-xwindow-id message.
        self.pipeline.addSyncBusHandler(self.prepareWindowCb)

    def getOverlay(self):
        return self.overlay

    def presetAspectRatio(self, presetAspect):
        # FIXME: Reimplement this by altering the caps before the video
        # sink.
        pass


    #
    # Internal Operations
    #

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

    def hidePointer(self):
        self.window.set_cursor(self.getInvisibleCursor())
        self.cursorTimeout = None
        return False


    #
    # Callbacks
    #

    def prepareWindowCb(self, bus, message):
        if not message.structure.has_name('prepare-xwindow-id'):
            return None

        self.overlay.set_xwindow_id(self.videoWin.xid)

        # Remove the callback from the pipeline.
        self.pipeline.removeSyncBusHandler(self.prepareWindowCb)

        return gst.BUS_DROP

    def sizeAllocateCb(self, widget, allocation):
        if not self.videoWin:
            return
        
        self.xlock.acquire()
        self.videoWin.move_resize(0, 0, allocation.width, allocation.height)
        self.xlock.release()

    def motionCb(self, widget, event):
        if self.cursorTimeout == None:
            self.window.set_cursor(None)
        else:
            gobject.source_remove(self.cursorTimeout)
        self.cursorTimeout = gobject.timeout_add(5000, self.hidePointer)

    def destroyCb(self, da):
        self.overlay.set_xwindow_id(0L)

    def backgroundRealizeCb(self, widget):
        # Create the video window.
        self.videoWin = gtk.gdk.Window(
            self.background.window,
            self.allocation.width, self.allocation.height,
            gtk.gdk.WINDOW_CHILD,
            gtk.gdk.EXPOSURE_MASK,
            gtk.gdk.INPUT_OUTPUT,
            "",
            0, 0)

        # Set a filter to trap expose events in the new window.
        self.videoWin.add_filter(self.videoEventFilterCb)

        self.videoWin.show()

        # Hide the pointer now.
        self.hidePointer()

        # We are ready to display video. The 'ready' signal could
        # actually set up the image sink.
        self.emit('ready')

    def videoEventFilterCb(self, event):
        # FIXME: Check for expose event here. Cannot be done now
        # because pygtk seems to have a bug and only reports "NOTHING"
        # events.
        self.xlock.acquire()

        self.overlay.expose()

        self.xlock.release()

        return gtk.gdk.FILTER_CONTINUE
