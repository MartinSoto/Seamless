import sys, os, popen2, signal

class LIRC(object):
    def __init__(self, name):
        self.conn = popen2.Popen3('ircat %s' % name)
        self.cmdFile = self.conn.fromchild

    def get(self):
        return self.cmdFile.readline()[:-1]

    def close(self):
        # Kill the ircat process explicitly.  Otherwise, this program
        # will hang forever.
        os.kill(self.conn.pid, signal.SIGTERM)
        os.waitpid(self.conn.pid, 0)


if __name__ == '__main__':
    lirc = LIRC("seamless")

    cmd = lirc.get()
    while cmd != 'off':
        print cmd
        sys.stdout.flush()
        cmd = lirc.get()

    lirc.close()
    print 'off'
    sys.stdout.flush()
