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

                'video',
                'topBox')

    def __init__(self, mainUi):
        super(MainWindow, self).__init__()

        self.mainUi = mainUi

        self.player = mainUi.getPlayer()
        options = mainUi.getOptions()

        self.mainUi.add_ui_from_string('''
        <ui>
          <toolbar name="toolbar">
            <toolitem action="up"/>
            <toolitem action="down"/>
            <toolitem action="left"/>
            <toolitem action="right"/>
            <toolitem action="confirm"/>
            <toolitem action="menu"/>
            <separator/>
            <toolitem action="pause"/>
            <toolitem action="prevProgram"/>
            <toolitem action="backward10"/>
            <toolitem action="forward10"/>
            <toolitem action="nextProgram"/>
          </toolbar>
        </ui>
        ''')

        self.set_title(_('Seamless DVD Player'))
        self.set_border_width(0)
        self.set_property('can-focus', True)
        
        self.connect('delete_event', self.mainDeleteEvent)

        vbox = gtk.VBox()
        self.add(vbox)

        self.topBox = gtk.VBox()
        vbox.pack_start(self.topBox, expand=False)

        toolbar = self.mainUi.get_widget('/toolbar')
        self.topBox.pack_start(toolbar, expand=False)

        self.video = videowidget.VideoWidget()
        vbox.pack_start(self.video)
        
        self.video.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.video.connect('ready', self.videoReady)
        self.video.connect('button-press-event', self.videoButtonPress)

        # FIXME: If the video sink doesn't support XOverlay, we have a
        # problem.
        self.video.setOverlay(self.player.getVideoSink())

        # Give the window a reasonable minimum size.
        self.set_size_request(480, 360)

        # Set the initial dimensions of the window to 75% of the screen.
        (rootWidth, rootHeight) = \
                    self.get_root_window().get_geometry()[2:4]
        self.set_default_size(int(rootWidth * 0.75),
                              int(rootHeight * 0.75))

        # Show the window with all of its subwidgets.
        self.show_all()

        # Set the full screen mode.
        self.fullScreen = options.fullScreen
        self.performFullScreen()


    #
    # Fullscreen Support
    #

    def isFullScreen(self):
        return self.fullScreen

    def performFullScreen(self):
        if self.fullScreen:
            self.fullscreen()
            self.topBox.hide()
            self.set_keep_above(1)
            self.video.grab_focus()
        else:
            self.unfullscreen()
            self.topBox.show()
            self.set_keep_above(0)

    def toggleFullScreen(self):
        self.fullScreen = not self.fullScreen
        self.performFullScreen()


    #
    # Callbacks
    #

    def mainDeleteEvent(self, widget, event):
        return False

    def videoReady(self, widget):
        # Start the player.
        self.player.start()

    def videoButtonPress(self, widget, event):
        self.toggleFullScreen()
