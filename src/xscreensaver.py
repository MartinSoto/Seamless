import os
import sys

import gobject

class XScreensaver(object):
    """Prevent xscreensaver from activating."""

    def __init__(self, mainUi):
        self.mainUi = mainUi

        # First stop xserver's screen blanking.
        os.system('xset s off')

        # Remember xscreensaver every 30 seconds that it shouldn't
        # start.
        self.sourceId = gobject.timeout_add(30000, self.timeout)

    def timeout(self):
        # Do any significant work in other process.
        if os.fork() == 0:
            # Redirect standard output to /dev/null to prevent
            # xscreensaver-command from cluterring the output.
            descr = os.open('/dev/null', os.O_WRONLY)
            os.dup2(descr, 1)
    
            try:
                os.execlp('xscreensaver-command', 'xscreensaver-command',
                          '-deactivate')
            except OSError:
                # xscreensaver-command not found. Deactivate the timeout.
                gobject.source_remove(self.sourceId)
        else:
            return True

    def close(self):
        gobject.source_remove(self.sourceId)

        # Reactivate screen blanking.
        os.system('xset s on')
