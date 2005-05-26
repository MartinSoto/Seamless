#!/usr/bin/python

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


import os
import string
import sys
from optparse import OptionParser

# Work around a bug in Python 2.3 that breaks gst-python.
os.environ['PYGTK_USE_GIL_STATE_API'] = '1'

import gobject
try:
    gobject.threads_init()
except:
    print "WARNING: gobject doesn't have threads_init, no threadsafety"

import pygtk
pygtk.require('2.0')
import gtk

# Get rid of the --help options before importing gst.
helpOpts = []
while '--help' in sys.argv:
    sys.argv.remove('--help')
    helpOpts = ['--help']

import gst

sys.argv.extend(helpOpts)

import player
import mainui

def main():
    progName = os.path.basename(sys.argv[0])

    # Parse the commandline.
    optParser = OptionParser()
    optParser.set_usage('Usage: %prog [options]')
    optParser.set_description("Seamless: A DVD player based on GStreamer")
    optParser.add_option("--fullscreen", dest="fullScreen",
                         action="store_true",
                         help="start in full screen mode")
    optParser.add_option("--path", dest="location",
                         metavar="PATH",
                         help="DVD device path is PATH",
                         default="/dev/dvd")
    optParser.add_option("--lirc", dest="lirc",
                         action="store_true",
                         help="enable lirc remote control support")
    optParser.add_option("--audio-sink", dest="audioSink",
                         metavar="SINK",
                         help="audio sink is SINK",
                         default="alsasink")
    optParser.add_option("--audio-decode", dest="audioDecode",
                         metavar="TYPE",
                         help="set type to 'hard' if the specified audio "
                         "sink decodes audio internally in hardware or "
                         "to 'soft' if it requires a software decoder",
                         default="soft",
                         choices = ('soft', 'hard'))
    optParser.add_option("--video-sink", dest="videoSink",
                         metavar="SINK",
                         help="video sink is SINK",
                         default="xvimagesink")
    optParser.add_option("--video-decode", dest="videoDecode",
                         metavar="TYPE",
                         help="'hard' if the specified video "
                         "sink decodes video internally in hardware or "
                         "'soft' (default) if it requires a software "
                         "decoder",
                         default="soft",
                         choices = ('soft', 'hard'))
    optParser.add_option("--clock", dest="clockType",
                         metavar="TYPE",
                         help="'robust' to use the special robust clock"
                         " (default), 'audiosink' to use the audio sink"
                         " clock or 'system' to use the system clock ",
                         default="robust",
                         choices = ('robust', 'audiosink', 'system'))
    (options, args) = optParser.parse_args()

    if args != []:
        optParser.error("invalid argument(s): %s" % string.join(args, ' '))

    # Use the fair scheduler.
    if gst.scheduler_factory_find('fairpth'):
        gst.scheduler_factory_set_default_name('fairpth')
    else:
        gst.scheduler_factory_set_default_name('fairgthread')

    # Create the main objects.
    playerObj = player.DVDPlayer(options)
    appInstance = mainui.MainUserInterface(playerObj, options)

    gtk.main()

if __name__ == "__main__":
    main()
