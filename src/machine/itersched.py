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

class NoIterError(IterSchedError):
    pass

class ExecutionError(IterSchedError):
    __slots__ = ('original', 'traceback')

    def __init__(self, original, traceback):
        IterSchedError.__init__(self)

        self.original = original
        self.traceback = traceback

    def __str__(self):
        return "\n%s%s: %s" % \
               (self.traceback, self.original.__class__.__name__,
                str(self.original))


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
        if not hasattr(iterator, 'next'):
            raise NoIterError

        self.instance = instance
        self.iter = iterator
        self.next = iterator.next

    def __iter__(self):
        return self

def restartPoint(method):
    def wrapper(self, *posArgs, **kwArgs):
        try:
            return RestartableIterator(self,
                                       method(self, *posArgs, **kwArgs))
        except NoIterError:
            raise NoIterError("Function or method '%s' (%s: %d) must "
                              "be a generator or return an iterator." % \
                              (method.func_name,
                               method.func_code.co_filename,
                               method.func_code.co_firstlineno))

    return wrapper


class Scheduler(object):
    __slots__ = ('current', 'stack')

    def __init__(self, rootIter):
        self.current = iter(rootIter)
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
            except Exception, e:
                import StringIO

                s = StringIO.StringIO()
                self.traceback(s)
                raise ExecutionError(e, s.getvalue())

    def __iter__(self):
        return self

    def call(self, itr):
        self.stack.append(self.current)
        if isinstance(itr, Scheduler):
            # Other schedulers get absorbed automatically.
            self.stack.extend(itr.stack)
            self.current = itr.current
        else:
            self.current = iter(itr)

    def chain(self, itr):
        if isinstance(itr, Scheduler):
            # Other schedulers get absorbed automatically.
            self.stack.extend(itr.stack)
            self.current = itr.current
        else:
            self.current = iter(itr)

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

    def restartable(self):
        """Iterate over the restartable instances in the scheduler.

        Returns an iterator that goes through the restartable object
        instances currently stacked in the scheduler. Last stacked
        instances are returned first."""
        if isinstance(self.current, RestartableIterator):
            yield self.current.instance
        for itr in reversed(self.stack):
            if isinstance(itr, RestartableIterator):
                yield itr.instance

    def traceback(self, out):
        """Print a traceback of the scheduler to the file 'out'."""
        # If anyone knows of a nicer way to get to the generator type,
        # please let me know.
        genType = (i for i in []).__class__

        print >> out, "Itersched traceback (most recent call last)"
        for item in self.stack + [self.current]:
            if isinstance(item, RestartableIterator):
                itr = item.iter
            else:
                itr = item

            if isinstance(itr, genType):
                print >> out, '  File "%s", line %d, in %s' % \
                      (itr.gi_frame.f_code.co_filename,
                       itr.gi_frame.f_lineno,
                       itr.gi_frame.f_code.co_name)
            else:
                print >> out, "  Object %s", str(itr)

__all__ = ('IterSchedError', 'NoIterError', 'ExecutionError',
           'NoOp', 'Call', 'Chain',
           'Restart', 'restartPoint', 'Scheduler')
