#!/usr/bin/python

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

import os
import string
import sys
from optparse import OptionParser

# Work around a bug in Python 2.3 that breaks gst-python.
os.environ['PYGTK_USE_GIL_STATE_API'] = '1'

# Activate the _() function.
import gettext
gettext.install('seamless')

import gobject
try:
    gobject.threads_init()
except:
    print _("WARNING: gobject doesn't have threads_init, no threadsafety")

import dbus
if getattr(dbus, 'version', (0,0,0)) >= (0,41,0):
    import dbus.glib

import pygtk
pygtk.require('2.0')
import gtk

# Get rid of the --help options before importing gst.
helpOpts = []
while '--help' in sys.argv:
    sys.argv.remove('--help')
    helpOpts = ['--help']

import pygst
pygst.require('0.10')
import gst

sys.argv.extend(helpOpts)

import player
import mainui
import message


class DictOptions(object):
    """A wrapper for the options object that adds dictionary behavior."""

    def __init__(self, options):
        self.__dict__['options'] = options

    def __getattr__(self, name):
        return getattr(self.options, name)

    def __setattr__(self, name, value):
        setattr(self.options, name, value)

    def __getitem__(self, key):
        return getattr(self.options, key)

    def __setitem__(self, name, value):
        setattr(self.options, name, value)    

    def __repr__(self):
        return repr(self.options)

    def __str__(self):
        return str(self.options)


def main():
    progName = os.path.basename(sys.argv[0])

    # Parse the commandline.
    optParser = OptionParser()
    optParser.set_usage(_('Usage: %prog [options]'))
    optParser.set_description(_("Seamless: A DVD player based on GStreamer"))
    optParser.add_option("--fullscreen", dest="fullScreen",
                         action="store_true",
                         help=_("start in full screen mode"))
    optParser.add_option("--device", dest="location",
                         metavar="PATH",
                         help=_("set path to DVD device to PATH"),
                         default="/dev/dvd")
    optParser.add_option("--region", dest="region",
                         metavar="REGION",
                         help=_("Set player's region to REGION. Possible "
                         "regions are: "
                         "0: Region free (not accepted by some DVDs); "
                         "1: U.S., Canada, U.S. Territories; "
                         "2: Japan, Europe, South Africa, and Middle "
                         "East (including Egypt); "
                         "3: Southeast Asia and East Asia (including "
                         "Hong Kong); "
                         "4: Australia, New Zealand, Pacific Islands, "
                         "Central America, Mexico, South America, "
                         "and the Caribbean; "
                         "5: Eastern Europe (Former Soviet Union), "
                         "Indian subcontinent, Africa, North Korea, "
                         "and Mongolia; "
                         "6: China; "
                         "7: Reserved; "
                         "8: Special international venues (airplanes, "
                         "cruise ships, etc.)"),
                         default=0)
    optParser.add_option("--audio-sink", dest="audioSink",
                         metavar="SINK",
                         help=_("audio sink is SINK"),
                         default="alsasink")
    optParser.add_option("--spdif-card", dest="spdifCard",
                         metavar="CARD",
                         help=_("Instead of decoding audio in software, "
                         "output raw AC3 and DTS to the SP/DIF "
                         "output in card CARD. CARD must be an audio "
                         "card name as defined by the ALSA driver (look "
                         "at the contents of your /proc/asound/cards "
                         "file). This option won't work if you don't "
                         "have the ALSA audio drivers installed and "
                         "configured in your machine"))
    optParser.add_option("--video-sink", dest="videoSink",
                         metavar="SINK",
                         help=_("video sink is SINK"),
                         default="xvimagesink")
    optParser.add_option("--pixel-aspect", dest="pixelAspect",
                         metavar="ASPECT",
                         help=_("set pixel aspect ratio to ASPECT "
                                "(default 1/1)"),
                         default="1/1")    
    optParser.add_option("--plugins", dest="plugins",
                         metavar="PLUGINS",
                         help=_("Enable Seamless plugins listed in "
                                "PLUGINS. PLUGINS is a comma separated "
                                "list"),
                         default="dpms,xscreensaver,gnomescreensaver")
    (options, args) = optParser.parse_args()
    options = DictOptions(options)

    if args != []:
        optParser.error(_("invalid argument(s): %s") % string.join(args, ' '))

    # Create the main objects.
    try:
        playerObj = player.DVDPlayer(options)
    except IOError, e:
        mainMsg = _("Cannot open DVD in path '%s'") % options.location
        secMsg = _("Your DVD drive could not be found. You may try to "
                   "use the --device command line option to specify the "
                   "correct device path to your drive. If you are sure"
                   " that you specified a valid path, verify that you "
                   "have read access to the device.")
        message.errorDialog(mainMsg, secMsg)
        return 1
    except gst.PluginNotFoundError, e:
        mainMsg = _("Cannot find GStreamer plugin '%s'") % str(e)
        secMsg = _("GStreamer is the multimedia system used by this "
                   "program to play video and audio, and it seems to "
                   "be installed incompletely or configured incorrectly"
                   " in your machine. Check your software installation"
                   " and try starting this program again.")
        message.errorDialog(mainMsg, secMsg)
        return 1
    except player.PipelineParseError, e:
        secMsg = _("A Gstreamer pipeline specified through the command"
                   " line options could not be parsed, or tried to use"
                   " unavailable GStreamer elements. Check your command"
                   " line and try again.")
        message.errorDialog(str(e), secMsg)
        return 1

    appInstance = mainui.MainUserInterface(playerObj, options)

    # Get into the main loop.
    gtk.main()
    return 0

if __name__ == "__main__":
    sys.exit(main())
