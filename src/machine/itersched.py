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


def checkItr(itr):
    assert hasattr(itr, 'next') and hasattr(itr, '__iter__'), \
           "Object '%s' is not an iterator" % repr(itr)


class YieldOp(object):
    __slots__ = ()

    def modifySched(self, sched):
        raise NotImplemented


class NoOpInstance(YieldOp):
    __slots__ = ()

    def modifySched(self, sched):
        pass

NoOp = NoOpInstance()
    

class Call(YieldOp):
    __slots__ = ('called')

    def __init__(self, called):
        checkItr(called)
        self.called = called

    def modifySched(self, sched):
        sched.call(self.called)


class Chain(YieldOp):
    __slots__ = ('chained')

    def __init__(self, chained):
        checkItr(chained)
        self.chained = chained

    def modifySched(self, sched):
        sched.chain(self.chained)
    

class RestartInstance(YieldOp):
    __slots__ = ('methodName', 'posArgs', 'kwArgs')

    def __init__(self, methodName, posArgs, kwArgs):
        self.methodName = methodName
        self.posArgs = posArgs
        self.kwArgs = kwArgs

    def modifySched(self, sched):
        sched.restart(self.methodName, *self.posArgs, **self.kwArgs)

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

def restartPoint(method):
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

                if isinstance(next, YieldOp):
                    next.modifySched(self)
                else:
                    return next
            except StopIteration:
                if len(self.stack) > 0:
                    self.current = self.stack.pop()
                else:
                    raise StopIteration

    def __iter__(self):
        return self

    def call(self, itr):
        self.stack.append(self.current)
        self.current = itr

    def chain(self, itr):
        self.current = itr

    def restart(self, methodName, *posArgs, **kwArgs):
        # Go down the stack searching for an instance having a method
        # with the specified name.
        while not isinstance(self.current, RestartableIterator) or \
                  not hasattr(self.current.instance, methodName):
            try:
                self.current = self.stack.pop()
            except IndexError:
                raise IterSchedError, \
                      "Restart of method '%s' failed" % methodName

        # Perform the actual restart.
        self.current = getattr(self.current.instance,
                               methodName)(*posArgs, **kwArgs)

    def getAttr(self, attrName):
        # Go down the stack searching for an instance having an
        # attribute with the specified name.
        if isinstance(self.current, RestartableIterator) and \
               hasattr(self.current.instance, attrName):
            return getattr(self.current.instance, attrName)

        for itr in reversed(self.stack):
            if isinstance(itr, RestartableIterator) and \
                   hasattr(itr, attrName):
                return getattr(self.current.instance, attrName)

    __getattr__ = getAttr


__all__ = ('IterSchedError', 'NoOp', 'Call', 'Chain', 'Restart',
           'restartPoint', 'Scheduler')
