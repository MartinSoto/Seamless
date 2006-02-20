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


class Plugin(object):
    """Prevent DPMS functions from activating when a movie is playing."""

    __slots__ = ('mainUi')

    def __init__(self, mainUi):
        self.mainUi = mainUi

        # Stop screen blanking and DPMS functions.
        os.system('xset -dpms')
        os.system('xset s off')

    def close(self):
        # Reactivate screen blanking and DPMS functions.
        os.system('xset s on')
        os.system('xset +dpms')

