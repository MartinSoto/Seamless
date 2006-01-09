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

import sys
import new
import re

import gobject
import gtk


class ActionGroup(gtk.ActionGroup):
    """A convenient wrapper for the gtk.ActionGroup class.

    Subclasses of this class can use the action, toggleAction and
    radioActions decorators below, to specify the gtk.Actions contained
    in the action group.

    When creating an instance of the subclass (which is of course also
    a gtk.ActionGroup instance) the arguments passed to the decorators
    at class definition time are used to construct gtk.Action
    instances that are automatically added to the new instance, and
    the decorated functions themselves are used as action
    callbacks. The callbacks don't receive the group instance itself
    as first parameter (i.e, no self parameter) but an instance of the
    gtk.UIManager passed as parameter to the constructor.

    Instances of the actions specified using the actions* decorators
    are also accesible as attributes of the UIManager passed as
    parameter to the constructor."""

    def __init__(self, uiManager, name=None):
        if name == None:
            name = self.__class__.__name__

        super(ActionGroup, self).__init__(name)

        if hasattr(self, '_ActionGroup_actions'):
            # Add the standard actions.
            for func, stockId, label, accel, tooltip in \
                self._ActionGroup_actions:
                action = gtk.Action(func.__name__, label, tooltip, stockId)
                action.connect('activate',
                               new.instancemethod(func, uiManager,
                                                  UIManager))
                setattr(uiManager, func.__name__, action)
                self.add_action_with_accel(action, accel)

        if hasattr(self, '_ActionGroup_toggle_actions'):
            # Add the toggle actions.
            for func, stockId, label, accel, tooltip, active in \
                self._ActionGroup_toggle_actions:
                action = gtk.ToggleAction(func.__name__, label, tooltip,
                                          stockId)
                action.set_active(active)
                action.connect('toggled',
                               new.instancemethod(func, uiManager, UIManager))
                setattr(uiManager, func.__name__, action)
                self.add_action_with_accel(action, accel)

        if hasattr(self, '_ActionGroup_radio_actions'):
            # Add the radio actions.
            for func, default, actionParams in \
                    self._ActionGroup_radio_actions:
                prevAction = None
                for number, (name, stockId, label, accel, tooltip) in \
                    actionParams.items():
                    action = gtk.RadioAction(name, label, tooltip, stockId,
                                             number)

                    if prevAction:
                        action.set_group(prevAction)
                    prevAction = action

                    if number == default:
                        action.set_active(True)

                    setattr(uiManager, name, action)
                    self.add_action_with_accel(action, accel)

                # Connect the callback to one arbitrary action.
                action.connect('changed',
                               new.instancemethod(func, uiManager, UIManager))



def action(stockId=None, label=None, accel=None, tooltip=None):
    locals = sys._getframe(1).f_locals

    lst = locals.get('_ActionGroup_actions')
    if not lst:
        # Initialize the list.
        lst = []
        locals['_ActionGroup_actions'] = lst

    def decorator(func):
        lst.append((func, stockId, label, accel, tooltip))
        return func
        
    return decorator

def toggleAction(stockId=None, label=None, accel=None, tooltip=None,
                 active=False):
    locals = sys._getframe(1).f_locals

    lst = locals.get('_ActionGroup_toggle_actions')
    if not lst:
        # Initialize the list.
        lst = []
        locals['_ActionGroup_toggle_actions'] = lst

    def decorator(func):
        lst.append((func, stockId, label, accel, tooltip, active))
        return func
        
    return decorator


_namePattern = re.compile('([a-z][a-zA-Z]+)([0-9]+)')
_validNames = ['name', 'stockId', 'label', 'accel', 'tooltip']

def radioActions(default, **keywords):
    locals = sys._getframe(1).f_locals

    # A mapping from radio action numbers to their parameters.
    actionParams = {}

    # Fill in the parameters using the function keyword arguments.
    for paramName, value in keywords.items():
        # Validate and parse the name.
        m = _namePattern.match(paramName)
        if not m or not m.group(1) in _validNames:
            raise TypeError, \
                  "radioActions() got an unexpected keyword argument '%s'" \
                  % paramName

        # Retrieve or create the parameter list for this action.
        number = int(m.group(2))
        try:
            params = actionParams[number]
        except KeyError:
            params = [None, None, None, None, None]
            actionParams[number] = params

        # Assign the actual value.
        params[_validNames.index(m.group(1))] = value

    # Check for actions without a name.
    for number, params in actionParams.items():
        if not params[0]:
            raise TypeError, "parameter 'name%d' must be specified" % number

    # The default action must exist.
    if not default in actionParams:
        raise ValueError, "default action %d not defined", default

    lst = locals.get('_ActionGroup_radio_actions')
    if not lst:
        # Initialize the list.
        lst = []
        locals['_ActionGroup_radio_actions'] = lst

    def decorator(func):
        lst.append((func, default, actionParams))
        return func
        
    return decorator


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
    """A convenient wrapper for the gtk.UIManager class.

    Subclasses of this class, can specify action groups by defining a
    contained class that derives (directly or indirectly) from
    ActionGroup in this module.

    When creating an instance of the subclass, instances of the
    specified actions groups will automatically be created and added
    to the manager. Such action groups are also accesible as
    attributes of the UIManager instance.
    """

    __metaclass__ = _CollectActionGroups

    def __init__(self, *args, **keywords):
        super(UIManager, self).__init__()

        assert self._UIManager_actionGroupClasses

        # Create one instance of each class and add it to self.
        pos = 0
        for groupClass in self._UIManager_actionGroupClasses:
            group = groupClass(self, *args, **keywords)
            setattr(self, group.get_name(), group)
            self.insert_action_group(group, pos)
            pos += 1

        
if __name__ == "__main__":

    # Test the module:

    obj = None
    cb = None
    aa = None
    ac = None

    class SomeActionGroup(ActionGroup):
        @action(stockId=gtk.STOCK_QUIT)
        def quit(ui, action):
            global obj, cb, aa
            obj = ui
            cb = 'quit'
            aa = action

        @action(label='Special', tooltip='Very special indeed')
        def special(ui, action):
            global obj, cb, aa
            obj = ui
            cb = 'special'
            aa = action

        @toggleAction(label='Flip', active=True)
        def flipflop(ui, action):
            global obj, cb, aa
            obj = ui
            cb = 'flipflop'
            aa = action

        @radioActions(default=2,
                      name1='yin', label1='Yin',
                      name2='yan', label2='Yan', stockId2=gtk.STOCK_OPEN,
                      tooltip2='The yan')
        def taoChanged(ui, action, current):
            global obj, cb, aa
            obj = ui
            cb = 'taoChanged'
            aa = action
            ac = current

    class DummyUi: pass
    dummyUi = DummyUi()

    ag = SomeActionGroup(dummyUi)
    assert ag.get_name() == 'SomeActionGroup'
    assert len(ag.list_actions()) == 5

    a = dummyUi.quit
    assert a == ag.get_action('quit')
    assert isinstance(a, gtk.Action)
    assert a.get_property('stock-id') == gtk.STOCK_QUIT
    a.activate()
    assert obj == dummyUi
    assert cb == 'quit'
    assert aa == a

    a = dummyUi.special
    assert a == ag.get_action('special')
    assert isinstance(a, gtk.Action)
    assert a.get_property('label') == 'Special'
    assert a.get_property('tooltip') == 'Very special indeed'
    a.activate()
    assert obj == dummyUi
    assert cb == 'special'
    assert aa == a

    a = dummyUi.flipflop
    assert a == ag.get_action('flipflop')
    assert isinstance(a, gtk.ToggleAction)
    assert a.get_active()
    assert a.get_property('label') == 'Flip'
    a.toggled()
    assert obj == dummyUi
    assert cb == 'flipflop'
    assert aa == a

    a = dummyUi.yin
    assert a == ag.get_action('yin')
    assert isinstance(a, gtk.RadioAction)
    assert not a.get_active()
    assert a.get_property('label') == 'Yin'

    a2 = dummyUi.yan
    assert a2 == ag.get_action('yan')
    assert isinstance(a2, gtk.RadioAction)
    assert a2.get_active()
    assert a2.get_property('label') == 'Yan'
    assert a2.get_property('stock-id') == gtk.STOCK_OPEN
    assert a2.get_property('tooltip') == 'The yan'

    a.activate()
    assert cb == 'taoChanged'
    assert aa == a or aa == a2
    assert a.get_current_value() == 1
    assert a.get_active()
    assert not a2.get_active()

    cb = None
    a2.activate()
    assert cb == 'taoChanged'
    assert aa == a or aa == a2
    assert a.get_current_value() == 2
    assert not a.get_active()
    assert a2.get_active()

    class SomeUIManager(UIManager):
        class actionGroup1(ActionGroup):
            @action(stockId=gtk.STOCK_QUIT)
            def quit(ui, action):
                global obj, cb, aa
                obj = ui
                cb = 'ui_quit'
                aa = action

        class actionGroup2(ActionGroup):
            @action(stockId=gtk.STOCK_QUIT)
            def quit2(ui, action):
                global obj, cb, aa
                obj = ui
                cb = 'ui_quit2'
                aa = action

        class Dummy(object):
            pass

    obj = None
    cb = None
    aa = None

    uim = SomeUIManager()

    assert len(uim.get_action_groups()) == 2
    assert isinstance(uim.actionGroup1, gtk.ActionGroup)
    assert len(uim.actionGroup1.list_actions()) == 1

    uim.quit.activate()
    assert obj == uim
    assert cb == 'ui_quit'
    assert aa == uim.quit
