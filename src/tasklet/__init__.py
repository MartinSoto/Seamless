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

from tasklet import *

def task(generator):
    """A decorator to convert a function into a tasklet."""

    def wrapper(*args, **keywords):
        return tasklet.run(generator(*args, **keywords))

    return wrapper

def initTask(generator):
    """A decorator to convert an __init__ method into a tasklet.

    Creating an object with such an __init__ method will automatically
    start the task. If the object has a writable `_mainTask'
    attribute, it will be set to task object."""

    def wrapper(self, *args, **keywords):
        taskObj = tasklet.run(generator(self, *args, **keywords))
        try:
            self._mainTask = taskObj
        except:
            pass

    return wrapper
