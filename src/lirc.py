import sys, os, popen2, signal

import gobject

class LIRC(object):
    def __init__(self, mainUi):
        self.mainUi = mainUi

        self.conn = popen2.Popen3('ircat seamless')
        self.cmdFile = self.conn.fromchild
        self.sourceId = gobject.io_add_watch(self.cmdFile,
                                             gobject.IO_IN,
                                             self.readData)

    def readData(self, source, condition):
        cmd = self.cmdFile.readline()[:-1]
        if cmd != 'off' and cmd != 'leave':
            print >> sys.stderr, "Command: %s" % cmd
            try:
                getattr(self.mainUi.getPlayer(), cmd)()
            except:
                traceback.print_exc()
                
            return True
        else:
            self.mainUi.shutDown()
            return False

    def close(self):
        gobject.source_remove(self.sourceId)

        # Kill the ircat process explicitly. Otherwise, this program
        # will hang forever.
        os.kill(self.conn.pid, signal.SIGTERM)
        os.waitpid(self.conn.pid, 0)

