# Seamless DVD Player
# Copyright (C) 2006 Martin Soto <martinsoto@users.sourceforge.net>
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

import dbus

class Plugin(object):
    """Prevent the Gnome screensaver from activating during a movie."""

    __slots__ = ('bus',
                 'saver')

    def __init__(self, mainUi):
        self.bus = dbus.SessionBus()
        self.saver = self.bus.get_object('org.gnome.ScreenSaver', 
                                         '/org/gnome/ScreenSaver')
        self.saver = dbus.Interface(self.saver, 'org.gnome.ScreenSaver')
        self.saver.InhibitActivation(_('Seamless: Playing video'))

    def close(self):
        self.saver.AllowActivation()