# Check if we have a libtool compilation directory and add it to the
# path.  This is necessary to be able to run directly from the
# development directory.
import sys, os
libtool_dir = os.path.join(__path__[0], '.libs')
if os.path.exists(libtool_dir):
   sys.path.append(libtool_dir)
del sys, os, libtool_dir

from _dvdread import *
