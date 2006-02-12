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

import sys, os, popen2, signal
import traceback

import gobject

class LIRC(object):
    def __init__(self, mainUi):
        self.mainUi = mainUi

        self.conn = popen2.Popen3('ircat seamless')
        self.cmdFile = self.conn.fromchild
        self.sourceId = gobject.io_add_watch(self.cmdFile,
                                             gobject.IO_IN,
                                             self.readData)

    def readData(self, source, condition):
        cmd = self.cmdFile.readline()[:-1]
        if cmd != 'off' and cmd != 'leave':
            try:
                getattr(self.mainUi.getPlayer(), cmd)()
            except:
                traceback.print_exc()
                
            return True
        else:
            self.mainUi.shutdown()
            return False

    def close(self):
        gobject.source_remove(self.sourceId)

        # Kill the ircat process explicitly. Otherwise, this program
        # will hang forever.
        os.kill(self.conn.pid, signal.SIGTERM)
        os.waitpid(self.conn.pid, 0)

