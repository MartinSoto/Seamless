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


class CallObject(object):
    __slots__ = ('called')

    def __init__(self, called):
        self.called = called


class Call(CallObject):
    pass


class RestartInstance(CallObject):
    __slots__ = ('methodName', 'posArgs', 'kwArgs')

    def __init__(self, methodName, posArgs, kwArgs):
        self.methodName = methodName
        self.posArgs = posArgs
        self.kwArgs = kwArgs

class RestartFactory(object):
    __slots__ = ()

    def __getattr__(self, name):
        return lambda *posArgs, **kwArgs: \
               RestartInstance(name, posArgs, kwArgs)

Restart = RestartFactory()


class RestartableIterator(object):
    __slots__ = ('instance', 'iter', 'next')

    def __init__(self, instance, iterator):
        self.instance = instance
        self.iter = iterator
        self.next = iterator.next

    def __iter__(self):
        return self

def restartable(method):
    def wrapper(self, *posArgs, **kwArgs):
        return RestartableIterator(self, method(self, *posArgs, **kwArgs))
        
    return wrapper


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
                    self.call(next.called)
                elif isinstance(next, RestartInstance):
                    self.restart(next.methodName, next.posArgs, next.kwArgs)
                else:
                    return next
            except StopIteration:
                if len(self.stack) > 0:
                    self.current = self.stack.pop()
                else:
                    raise StopIteration

    def __iter__(self):
        return self

    def call(self, restartable):
        assert isinstance(restartable, RestartableIterator)

        self.stack.append(self.current)
        self.current = restartable

    def restart(self, methodName, posArgs, kwArgs):
        # Go down the stack searching for an instance having a method
        # with the specified name.
        while not hasattr(self.current.instance, methodName):
            try:
                self.current = self.stack.pop()
            except IndexError:
                raise IterSchedError, \
                      "Restart of method '%s' failed" % methodName

        # Perform the actual restart.
        self.current = getattr(self.current.instance,
                               methodName)(*posArgs, **kwArgs)
