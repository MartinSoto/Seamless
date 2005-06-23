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


"""GObject style signals implemented in pure python."""

class SignalHolder(object):
    """A base classes for all classes holding signals."""

    __slots__ = ('__signals')


class signal(object):
    """A descriptor for signals."""

    __slots__ = ('defHandler',
                 'name')

    def __init__(self, defHandler):
        self.defHandler = defHandler
        self.name = defHandler.__name__

    def __get__(self, obj, type=None):
        try:
            return obj._SignalHolder__signals[self.name]
        except KeyError:
            s = Signal(obj, self.defHandler)
            obj._SignalHolder__signals[self.name] = s
            return s
        except AttributeError:
            s = Signal(obj, self.defHandler)
            obj._SignalHolder__signals = {self.name: s}
            return s

    def __set__(self, obj, value):
        raise AttributeError, 'Signals are read-only'


class Signal(object):
    """An object representing a signal."""

    __slots__ = ('obj',
                 'handlers')
    
    def __init__(self, obj, defHandler):
        self.obj = obj
        self.handlers = [defHandler]

    def __call__(self, *args, **keywords):
        for h in self.handlers:
            h(self.obj, *args, **keywords)

    def connect(self, f, passInstance=True):
        if passInstance:
            handler = f
        else:
            # Don't pass the object to this handler.
            handler = lambda obj, *args, **keywords: f(*args, **keywords)

        self.handlers.append(handler)

    def disconnect(self, f):
        while f in self.handlers:
            self.handlers.remove(f)


__all__ = ('SignalHolder', 'signal')
