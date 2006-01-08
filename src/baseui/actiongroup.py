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

import gtk


class ActionGroup(gtk.ActionGroup):
    """A convenient wrapper for the gtk.ActionGroup class."""

    def __init__(self, name=None):
        if name == None:
            name = self.__class__.__name__

        super(ActionGroup, self).__init__(name)

        if hasattr(self, '_ActionGroup_actions'):
            # Add the standard actions.
            for func, stockId, label, accel, tooltip in \
                self._ActionGroup_actions:
                action = gtk.Action(func.__name__, label, tooltip, stockId)
                action.connect('activate',
                               new.instancemethod(func, self, ActionGroup))
                self.add_action_with_accel(action, accel)

        if hasattr(self, '_ActionGroup_toggle_actions'):
            # Add the toggle actions.
            for func, stockId, label, accel, tooltip, active in \
                self._ActionGroup_toggle_actions:
                action = gtk.ToggleAction(func.__name__, label, tooltip,
                                          stockId)
                action.set_active(active)
                action.connect('toggled',
                               new.instancemethod(func, self, ActionGroup))
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

                    self.add_action_with_accel(action, accel)

                # Connect the callback to one arbitrary action.
                action.connect('changed',
                               new.instancemethod(func, self, ActionGroup))



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


if __name__ == "__main__":

    cb = None
    aa = None
    ac = None

    class SomeActionGroup(ActionGroup):
        @action(stockId=gtk.STOCK_QUIT)
        def quit(self, action):
            global cb, aa
            cb = 'quit'
            aa = action

        @action(label='Special', tooltip='Very special indeed')
        def special(self, action):
            global cb, aa
            cb = 'special'
            aa = action

        @toggleAction(label='Flip', active=True)
        def flipflop(self, action):
            global cb, aa
            cb = 'flipflop'
            aa = action

        @radioActions(default=2,
                      name1='yin', label1='Yin',
                      name2='yan', label2='Yan', stockId2=gtk.STOCK_OPEN,
                      tooltip2='The yan')
        def taoChanged(self, action, current):
            global cb, aa
            cb = 'taoChanged'
            aa = action
            ac = current

    ag = SomeActionGroup()
    assert ag.get_name() == 'SomeActionGroup'
    assert len(ag.list_actions()) == 5

    a = ag.get_action('quit')
    assert isinstance(a, gtk.Action)
    assert a.get_property('stock-id') == gtk.STOCK_QUIT
    a.activate()
    assert cb == 'quit'
    assert aa == a

    a = ag.get_action('special')
    assert isinstance(a, gtk.Action)
    assert a.get_property('label') == 'Special'
    assert a.get_property('tooltip') == 'Very special indeed'
    a.activate()
    assert cb == 'special'
    assert aa == a

    a = ag.get_action('flipflop')
    assert isinstance(a, gtk.ToggleAction)
    assert a.get_active()
    assert a.get_property('label') == 'Flip'
    a.toggled()
    assert cb == 'flipflop'
    assert aa == a

    a = ag.get_action('yin')
    assert isinstance(a, gtk.RadioAction)
    assert not a.get_active()
    assert a.get_property('label') == 'Yin'

    a2 = ag.get_action('yan')
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

