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

import gtk

import videowidget


class MainWindow(gtk.Window):
    """The Seamless main window."""
    
    __slots_ = ('mainUi',

                'player',

                'topBox',
                'video',
                'leaveFullScreenBox',

                'fullScreenActive')

    def __init__(self, mainUi):
        super(MainWindow, self).__init__()

        self.mainUi = mainUi

        self.player = mainUi.getPlayer()

        # Give the window a reasonable minimum size.
        self.set_size_request(480, 360)

        # Set the initial dimensions of the window to 75% of the screen.
        (rootWidth, rootHeight) = \
                    self.get_root_window().get_geometry()[2:4]
        self.set_default_size(int(rootWidth * 0.75),
                              int(rootHeight * 0.75))

        # Define the toolbar.
        self.mainUi.add_ui_from_string('''
        <ui>
          <toolbar name="toolbar">
            <toolitem action="menu"/>

            <separator/>

            <toolitem action="pause"/>

            <separator/>

            <toolitem action="prevProgram"/>
            <toolitem action="backward10"/>
            <toolitem action="forward10"/>
            <toolitem action="nextProgram"/>

            <separator/>

            <toolitem action="fullScreen"/>
          </toolbar>

          <accelerator action="menu"/>

          <accelerator action="pause"/>

          <accelerator action="prevProgram"/>
          <accelerator action="nextProgram"/>
          <accelerator action="backward10"/>
          <accelerator action="forward10"/>

          <accelerator action="nextAudioStream"/>
          <accelerator action="nextAngle"/>

          <accelerator action="quit"/>

          <accelerator action="debugConsoleAsync"/>
        </ui>
        ''')

        # Add the central AccelGroup to the window.
        accelgroup = mainUi.get_accel_group()
        self.add_accel_group(accelgroup)

        self.set_title(_('Seamless DVD Player'))
        self.set_border_width(0)
        self.set_property('can-focus', True)

        self.connect('configure-event', self.mainConfigureEvent)
        self.connect('delete_event', self.mainDeleteEvent)

        vbox = gtk.VBox()
        vbox.show()
        self.add(vbox)

        # An additional box makes it possible to hide/show all top
        # elements in a single operation.
        self.topBox = gtk.VBox()
        vbox.pack_start(self.topBox, expand=False)

        toolbar = self.mainUi.get_widget('/toolbar')
        toolbar.show()
        self.topBox.pack_start(toolbar, expand=False)

        self.video = videowidget.VideoWidget()
        self.video.show()
        vbox.pack_start(self.video)
        self.video.set_property('can-focus', True)
        self.video.connect('key-press-event', self.videoKeyPress)
        self.video.connect('ready', self.videoReady)
        self.video.grab_focus()

        self.video.setCursorTimeout(None)

        # FIXME: If the video sink doesn't support XOverlay, we have a
        # problem.
        self.video.setOverlay(self.player.getVideoSink())

        # A table container allows us to lay widgets on top of the
        # video display.
        table = gtk.Table(3, 3)
        table.show()
        self.video.add(table)

        # An expansive empty label in the middle position forces
        # widgets in the corners to shrink to their natural sizes.
        expandLabel = gtk.Label()
        expandLabel.show()
        table.attach(expandLabel, left_attach=1, right_attach=2,
                     top_attach=1, bottom_attach=2)

        # The fullscreen cancel button. In order for widgets to be
        # visible on top of the video overlay, they must have a
        # window. For this reason we put the button in an event box.
        self.leaveFullScreenBox = gtk.EventBox()
        table.attach(self.leaveFullScreenBox, left_attach=2, right_attach=3,
                     top_attach=0, bottom_attach=1,
                     xoptions=0, yoptions=0, xpadding=10, ypadding=10)
        
        leaveFullScreen = gtk.Button(stock=gtk.STOCK_LEAVE_FULLSCREEN)
        leaveFullScreen.show()
        leaveFullScreen.connect('clicked', self._leaveFullScreenClicked)
        self.leaveFullScreenBox.add(leaveFullScreen)

        # No fullscreen by default.
        self.fullScreenActive = False
        self.video.connect('cursor-hidden', self._videoCursorHidden)
        self.video.connect('cursor-shown', self._videoCursorShown)


    #
    # Full Screen Support
    #

    def fullScreen(self, activate):
        self.fullScreenActive = activate
        if activate:
            self.topBox.hide()
            self.video.grab_focus()
            self.video.setCursorTimeout(5)
            self.fullscreen()
            self.set_keep_above(1)
            self.leaveFullScreenBox.show()
        else:
            self.leaveFullScreenBox.hide()
            self.unfullscreen()
            self.set_keep_above(0)
            self.topBox.show()
            self.video.setCursorTimeout(None)

    def _videoCursorHidden(self, widget):
        if self.fullScreenActive:
            self.leaveFullScreenBox.hide()

    def _videoCursorShown(self, widget):
        if self.fullScreenActive:
            self.leaveFullScreenBox.show()

    def _leaveFullScreenClicked(self, widget):
        self.mainUi.fullScreen.set_active(False)


    #
    # Callbacks
    #

    def mainConfigureEvent(self, widget, event):
        self.video.forceVideoUpdate()

    def mainDeleteEvent(self, widget, event):
        return False

    def videoReady(self, widget):
        # Start the player.
        self.player.start()

    def videoKeyPress(self, widget, event):
        keyName = gtk.gdk.keyval_name(event.keyval)

        # These five actions must be handled here explicitly since
        # their corresponding keys cannot be used in accelerators.
        if keyName == 'Up':
            self.mainUi.up.activate()
        elif keyName == 'Down':
            self.mainUi.down.activate()
        elif event.state == 0 and keyName == 'Left':
            self.mainUi.left.activate()
        elif event.state == 0 and keyName == 'Right':
            self.mainUi.right.activate()
        elif keyName == 'Return':
            self.mainUi.confirm.activate()
        elif keyName == 'Escape':
            self.mainUi.fullScreen.set_active(False)
        else:
            return False

        return True
