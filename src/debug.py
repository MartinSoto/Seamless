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

import code
import threading

import gst

def debugConsole(player):
    """Start a debug Python console in the controlling terminal.

    The program execution is suspended during the execution of the
    console. Once the console terminates the program continues
    executing normally."""
    code.interact('Seamless debug console', None,
                  {'player': player,
                   'info': player.info,
                   'machine': player.machine,
                   'pipeline': player.pipeline,
                   'manager': player.manager})

def debugConsoleAsync(player):
    """Start a debug console in the controlling terminal.

    The program execution continues concurrently with the
    console. This means that the console can peek into the running
    program. It is also possible to change values, but this is not
    guaranteed to be safe."""
    t = threading.Thread(None, debugConsole, 'Debug console', (player,))
    t.start()


def enterLeave(func):
    def wrapper(*args, **keywords):
        gst.debug("Entering '%s'" % func.__name__)

        value = func(*args, **keywords)

        if value == None:
            gst.debug("Leaving '%s'" % func.__name__)
        else:
            gst.debug("Leaving '%s' with value '%s'" % (func.__name__,
                                                        str(value)))
            return value

    wrapper.__name__ = func.__name__
    return wrapper
