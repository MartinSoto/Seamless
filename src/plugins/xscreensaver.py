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

import gobject

class Plugin(object):
    """Prevent xscreensaver from activating while a movie is playing."""

    def __init__(self, mainUi):
        self.mainUi = mainUi

        # Remember xscreensaver every 30 seconds that it shouldn't
        # start.
        self.sourceId = gobject.timeout_add(30000, self.timeout)

    def timeout(self):
        # Do the work in another process.
        pid = os.fork()
        if pid == 0:
            # Redirect standard output and error to /dev/null to prevent
            # xscreensaver-command from cluttering the output.
            descr = os.open('/dev/null', os.O_WRONLY)
            os.dup2(descr, 1)
            descr = os.open('/dev/null', os.O_WRONLY)
            os.dup2(descr, 2)
    
            try:
                os.execlp('xscreensaver-command', 'xscreensaver-command',
                          '-deactivate')
            except OSError:
                # xscreensaver-command not found. Deactivate the timeout.
                gobject.source_remove(self.sourceId)
                return False
        else:
            pid, status = os.waitpid(pid, 0)

            if status & 0xff != 0 or status >> 8 != 0:
                # Something went wrong while calling
                # xscreensaver-command. Deactivate the timeout.
                gobject.source_remove(self.sourceId)
                return False

            return True

    def close(self):
        gobject.source_remove(self.sourceId)
