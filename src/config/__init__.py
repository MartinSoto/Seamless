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

# This package is used only to configure Seamless to work locally
# without requiring an installation. Installed versions of Seamless
# use a generated config.py file.

import os
import sys

# Suffix for plugin files.
pluginSuffix = '.so'

# Base source directory.
base = os.path.split(os.path.split(__path__[0])[0])[0]

# Directory containing the GStreamer plugins.
gstPlugins = os.path.join(base, 'gst-plugins')

# Directory contaning all glade files.
gladeDir = os.path.join(base, 'glade')

__all__ = (pluginSuffix, gstPlugins, glade)
