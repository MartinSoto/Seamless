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

import threading

import gobject
import gtk

import gst
import gst.interfaces

import tasklet


class VideoWidget(gtk.EventBox):
    __slots__ = ('overlay',
                 'pipeline',

                 'cursorHidden'
                 'invisibleCursorObj'
                 'cursorTimeout',
                 'cursorTask',

                 'overlaySet')

    __gsignals__ = {
        'ready' : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE,
                   ()),
        'cursor-shown' : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE,
                          ()),
        'cursor-hidden' : (gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE,
                           ())
        }


    @tasklet.initTask
    def __init__(self):
        super(VideoWidget, self).__init__()

        # When double buffering is active, Gtk ends up painting on top
        # of the overlay color, thus completely breaking the video
        # display.
        self.set_double_buffered(False)
        self.set_app_paintable(True)

        # A lock to protect accesses to the display window.
        self.xlock = threading.RLock()

        self.set_events(gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.BUTTON_PRESS_MASK)
        self.connect('delete-event', self.deleteCb)
        self.connect('button-press-event', self.buttonPressCb)

        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))

        self.overlay = None

        self.cursorTimeout = None
        self.cursorTask = None

        # The video overlay window is not yet set.
        self.overlaySet = False

        # Wait until we have an actual window.
        yield tasklet.WaitForSignal(self, 'map-event')
        tasklet.get_event()

        # Create an invisible cursor object.
        display = self.get_display()
        assert display
        pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 1, 1)
        pixbuf.fill(0x00000000)
        self.invisibleCursorObj = gtk.gdk.Cursor(display, pixbuf, 0, 0);
        
        # Force one emission of the 'cursor-shown' signal.
        self.cursorHidden = True
        self._showCursor()

        # Start the cursor task.
        self.cursorTask = self._updateCursor()

        # We are ready to display video. The 'ready' signal could
        # actually set up the image sink.
        self.emit('ready')


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


    #
    # Expose
    #

    def do_expose_event(self, event):
        self.xlock.acquire()
        self.overlay.expose()
        self.xlock.release()

        return True

    def forceVideoUpdate(self):
        """Force an update of the video display. This is used to keep
        the video properly repainted when the main window is moved
        without exposing any new area."""
        if self.overlaySet:
            self.xlock.acquire()
            self.overlay.expose()
            self.xlock.release()


    #
    # Cursor
    #

    def _showCursor(self):
        if self.cursorHidden:
            self.window.set_cursor(None)
            self.cursorHidden = False
            self.emit('cursor-shown')

    def _hideCursor(self):
        if not self.cursorHidden:
            self.window.set_cursor(self.invisibleCursorObj)
            self.cursorHidden = True
            self.emit('cursor-hidden')

    @tasklet.task
    def _updateCursor(self):
        update = tasklet.WaitForMessages(accept='timeoutUpdated')
        motion = tasklet.WaitForSignal(self, 'motion-notify-event')
        delete = tasklet.WaitForSignal(self, 'delete-event')

        while True:
            if self.cursorTimeout == None:
                # Cursor always visible, check only for updates.
                yield (update, delete)
            elif self.cursorHidden:
                # Cursor already hidden, no further timeout check.
                yield (update, motion, delete)
            else:
                yield (update, motion, delete,
                       tasklet.WaitForTimeout(1000 * self.cursorTimeout))
            event = tasklet.get_event()

            if isinstance(event, tasklet.WaitForSignal) and \
                   event.signal == 'delete-event':
                # Finish the task.
                return
            elif isinstance(event, tasklet.WaitForTimeout):
                # Blink the cursor.
                on = False
                for i in range(10):
                    if on:
                        self.window.set_cursor(None)
                    else:
                        self.window.set_cursor(self.invisibleCursorObj)

                    yield (update, motion, delete,
                           tasklet.WaitForTimeout(200))
                    event = tasklet.get_event()
                    
                    if isinstance(event, tasklet.WaitForSignal) and \
                           event.signal == 'delete-event':
                        return
                    elif isinstance(event, tasklet.WaitForTimeout):
                        on = not on
                    else:
                        self.window.set_cursor(None)
                        self._showCursor()
                        break

                if isinstance(event, tasklet.WaitForTimeout):
                    # We left the loop because of a timeout. The
                    # blinking time is complete.
                    self._hideCursor()
            else:
                self._showCursor()

    @tasklet.task
    def setCursorTimeout(self, timeout):
        assert timeout == None or timeout >= 0

        self.cursorTimeout = timeout
        # Tell the cursor task that the timeout was updated.
        if self.cursorTask:
            yield tasklet.Message(name='timeoutUpdated',
                                  dest=self.cursorTask)


    #
    # Callbacks
    #

    def prepareWindowCb(self, bus, message):
        if not message.structure.has_name('prepare-xwindow-id'):
            return None

        self.overlay.set_xwindow_id(self.window.xid)
        self.overlaySet = True

        # Remove the callback from the pipeline.
        self.pipeline.removeSyncBusHandler(self.prepareWindowCb)

        return gst.BUS_DROP

    def deleteCb(self, da):
        self.overlay.set_xwindow_id(0L)
        set.overlaySet = False

    def buttonPressCb(self, widget, event):
        # We send button press navigation events "by hand" here, since
        # Gtk seems to prevent the GStreamer elements from doing so.
        self.overlay.send_mouse_event ('mouse-button-press',
                                       event.button, event.x, event.y)
