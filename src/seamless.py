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

import pygst
pygst.require('0.10')
import gst

sys.argv.extend(helpOpts)

import player
import mainui


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
    optParser.set_usage('Usage: %prog [options]')
    optParser.set_description("Seamless: A DVD player based on GStreamer")
    optParser.add_option("--fullscreen", dest="fullScreen",
                         action="store_true",
                         help="start in full screen mode")
    optParser.add_option("--device", dest="location",
                         metavar="PATH",
                         help="set path to DVD device to PATH",
                         default="/dev/dvd")
    optParser.add_option("--lirc", dest="lirc",
                         action="store_true",
                         help="enable lirc remote control support")
    optParser.add_option("--audio-sink", dest="audioSink",
                         metavar="SINK",
                         help="audio sink is SINK",
                         default="alsasink")
    optParser.add_option("--spdif-card", dest="spdifCard",
                         metavar="CARD",
                         help="Instead of decoding audio in software, "
                         "output raw AC3 and DTS to the SP/DIF "
                         "output in card CARD. CARD must be an audio "
                         "card name as defined by the ALSA driver (look "
                         "at the contents of your /proc/asound/cards "
                         "file). This option won't work if you don't "
                         "have the ALSA audio drivers installed and "
                         "configured in your machine")
    optParser.add_option("--video-sink", dest="videoSink",
                         metavar="SINK",
                         help="video sink is SINK",
                         default="xvimagesink")
    optParser.add_option("--pixel-aspect", dest="pixelAspect",
                         metavar="ASPECT",
                         help="set pixel aspect ratio to ASPECT (default 1.0)",
                         default="1.0")    
    optParser.add_option("--clock", dest="clockType",
                         metavar="TYPE",
                         help="'robust' to use the special robust clock"
                         " (default), 'audiosink' to use the audio sink"
                         " clock or 'system' to use the system clock ",
                         default="robust",
                         choices = ('robust', 'audiosink', 'system'))
    (options, args) = optParser.parse_args()
    options = DictOptions(options)

    if args != []:
        optParser.error("invalid argument(s): %s" % string.join(args, ' '))

    # Evaluate the pixel aspect ratio.
    try:
        options.pixelAspect = eval(options.pixelAspect, {}, {})
    except:
        optParser.error("invalid expression '%s'" % options.pixelAspect)
    if options.pixelAspect < 1.0 or options.pixelAspect > 10.0:
        optParser.error("value %0.3f out of range for pixel aspect ratio" %
                        options.pixelAspect)

    # Create the main objects.
    playerObj = player.DVDPlayer(options)
#     appInstance = mainui.MainUserInterface(playerObj, options)

#     gtk.main()
    playerObj.start()
    gobject.MainLoop().run()

if __name__ == "__main__":
    main()
