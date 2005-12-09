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

import config

import os
import sys

import gst

# Loaded plugins must be kept in a list in order to guarantee they are
# referenced until the end of the execution of the whole program.
pluginList = []

registry = gst.registry_get_default()

# Search for all plugin files and try to register them.
for root, dirs, files in os.walk(config.gstPlugins):
   for file in files:
      if file[-len(config.pluginSuffix):] == config.pluginSuffix:
         plugin = gst.plugin_load_file(os.path.join(root, file))
         if plugin:
            pluginList.append(plugin)
            registry.add_plugin(plugin)

# Don't export any actual symbols.
__all__ = []
