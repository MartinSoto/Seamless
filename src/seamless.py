#!/usr/bin/python2.3

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

import dvdplayer
import mainui

def main():
    progName = os.path.basename(sys.argv[0])

    # Parse the commandline.
    optParser = OptionParser()
    optParser.set_usage('Usage: %prog [options]')
    optParser.set_description("Seamless: A DVD player based on GStreamer")
    optParser.add_option("--path", dest="path",
                         metavar="PATH",
                         help="DVD device path is PATH",
                         default="/dev/dvd")
    optParser.add_option("--fullscreen", dest="fullScreen",
                         action="store_true",
                         help="start in full screen mode")
    (options, args) = optParser.parse_args()

    if args != []:
        optParser.error("invalid argument(s): %s" % string.join(args, ' '))

    # Use the fair scheduler.
    gst.scheduler_factory_set_default_name('fairpth')
    #gst.scheduler_factory_set_default_name('fairgthread')

    # Create the main objects.
    player = dvdplayer.DVDPlayer(location=options.path)
    appInstance = mainui.MainUserInterface(player,
                                           fullScreen=options.fullScreen)

    gtk.main()

if __name__ == "__main__":
    main()
