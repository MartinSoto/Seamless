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
            print 'new value'
            s = Signal(obj, self.defHandler)
            obj._SignalHolder__signals[self.name] = s
            return s
        except AttributeError:
            print 'new attrib'
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

    def connect(self, f):
        self.handlers.append(f)

    def disconnect(self, f):
        while f in self.handlers:
            self.handlers.remove(f)


__all__ = ('SignalHolder', 'signal')
