import sys
import os

from dvdplayer import *
from list import *

#scheduler_factory_set_default_name ('fairpth')
#scheduler_factory_set_default_name ('fairgthread')

player = DVDPlayer('player')

vmg = player.info.videoManager

#os.spawnlp(os.P_WAIT, 'givertcap')

player.start()

def jp(title, chapter):
    player.jump(vmg.getVideoTitle(title).getChapter(chapter))

def tj(time):
    player.timeJump(time)

def st():
    player.stop()
    sys.exit(0)

def bk():
    player.timeJumpRelative(-10)
    print player.currentTime

def fw():
    player.timeJumpRelative(10)
    print player.currentTime

