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

class IterSchedError(Exception):
    pass

class Call(object):
    __slots__ = ('called')

    def __init__(self, called):
        self.called = called


class Restart(object):
    __slots__ = ()


class Scheduler(object):
    __slots__ = ('current', 'stack')

    def __init__(self, rootIter):
        self.current = rootIter
        self.stack = []

    def next(self):
        while True:
            try:
                next = self.current.next()

                if isinstance(next, Call):
                    self.stack.append(self.current)
                    self.current = next.called
                elif isinstance(next, Restart):
                    # The scheduler is restarting, the next iteration
                    # will complete the job.
                    pass
                else:
                    return next
            except StopIteration:
                if len(self.stack) > 0:
                    self.current = self.stack.pop()
                else:
                    raise StopIteration

    def __iter__(self):
        return self

    def __getattr__(self, methodName):
        # Find an object in the stack having an attribute
        # with the specified name.
        while not hasattr(self.current, methodName):
            try:
                self.current = self.stack.pop()
            except IndexError:
                raise IterSchedError, "No method '%s' found " \
                      "while attempting to restart" % \
                      methodName
        method = getattr(self.current, methodName)

        def wrapper(*posArgs, **kwArgs):
            method(*posArgs, **kwArgs)

            # Return a Restart object to allow for restarts to be
            # "yielded".
            return Restart()

        return wrapper


def restartEntry(method):
    def wrapper(self, *posArgs, **kwArgs):
        iter = method(self, *posArgs, **kwArgs)
        self.__iter = iter
        self.next = iter.next

    return wrapper
