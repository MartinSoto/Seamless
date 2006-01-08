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

import gobject
import gtk

from actiongroup import ActionGroup


class _CollectActionGroups(gobject.GObjectMeta):
    """A metaclass to collect any action groups defined inside the
    class into a list also stored in the class' dictionary."""

    def __init__(cls, name, bases, dict):
        super(_CollectActionGroups, cls).__init__(name, bases, dict)

        groupClasses = []
        cls._UIManager_actionGroupClasses = groupClasses

        for name, obj in dict.items():
            if isinstance(obj, type) and issubclass(obj, ActionGroup):
                groupClasses.append(obj)


class UIManager(gtk.UIManager):
    """A convenient wrapper for the gtk.UIManager class."""

    __metaclass__ = _CollectActionGroups

    def __init__(self, *args, **keywords):
        super(UIManager, self).__init__()

        assert self._UIManager_actionGroupClasses

        # Create one instance of each class and add it to self.
        pos = 0
        for groupClass in self._UIManager_actionGroupClasses:
            group = groupClass(*args, **keywords)
            setattr(self, group.get_name(), group)
            self.insert_action_group(group, pos)
            pos += 1

        
if __name__ == "__main__":
    from actiongroup import action

    class SomeUIManager(UIManager):
        class actionGroup1(ActionGroup):
            @action(stockId=gtk.STOCK_QUIT)
            def quit(self, action):
                global cb, aa
                cb = 'quit'
                aa = action

        class actionGroup2(ActionGroup):
            @action(stockId=gtk.STOCK_QUIT)
            def quit(self, action):
                global cb, aa
                cb = 'quit'
                aa = action

        class Dummy(object):
            pass

    uim = SomeUIManager()

    assert len(uim.get_action_groups()) == 2
    assert isinstance(uim.actionGroup1, gtk.ActionGroup)
    assert len(uim.actionGroup1.list_actions()) == 1
