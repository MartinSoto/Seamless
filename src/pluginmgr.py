# Seamless DVD Player
# Copyright (C) 2006 Martin Soto <martinsoto@users.sourceforge.net>
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


class PluginManager(object):
    """A manager for Python plugins for Seamless."""

    __slots__ = ('instances')

    def __init__(self):
        self.instances = {}

    def loadPlugin(self, name, *args):
        if name in self.instances:
            # Don't reload plugins.
            return None

        try:
            # A plugin is just a module somewhere in sys.path:
            plugin = __import__(name)
            components = name.split('.')
            for comp in components[1:]:
                plugin = getattr(plugin, comp)

            # It should contain a factory (usually a class) called
            # 'Plugin'.
            factory = plugin.Plugin

            # Create an instance using the arguments.
            self.instances[name] = factory(*args)
        except Exception, e:
            return e

        return None

    def closePlugins(self):
        errors = []

        for name, instance in self.instances.items():
            try:
                instance.close()
            except Exception, e:
                errors.append((name, e))

        return errors
