import sys
from disassemble import *


def listCmds(pgc):
    print "Pre commands:"
    openIndent()
    for i in range(pgc.preCommandCount):
        showCmd(pgc.getPreCommand(i + 1), i + 1)
    print
    closeIndent()

    print "Post commands:"
    openIndent()
    for i in range(pgc.postCommandCount):
        showCmd(pgc.getPostCommand(i + 1), i + 1)
    print
    closeIndent()

    print "Cell commands:"
    openIndent()
    for i in range(pgc.cellCommandCount):
        showCmd(pgc.getCellCommand(i + 1), i + 1)
    print
    closeIndent()


# from dvdread import *

# manager = DVDInfo('/dev/dvd').videoManager
# fp=manager.firstPlay

# pgc=manager.getVideoTitle(2).getChapter(1).programChain
# listCmds(pgc)


if __name__ == '__main__':
    d = CommandDisassembler()

    testCmds = (
        ('00 00 00 00 00 00 00 00',
         'Nop'),
        ('00 01 00 00 00 00 00 07',
         'GoTo Line 7'),
        ('00 03 00 00 00 00 03 64',
         'settmppml level=3,goto 100'),
        ('00 32 00 01 00 81 00 00',
         'If (GPRM1 != SPRM1) Break'),
        ('00 A1 00 03 00 03 00 49',
         'If (GPRM3 == 3) GoTo Line 73'),
        ('20 04 00 00 00 00 03 56',
         'LinkPGCN 854'),
        ('20 06 00 00 00 00 00 AE',
         'LinkPGN 174,button 0'),
        ('20 16 00 05 00 0A 14 04',
         'If (GPRM5 & GPRM10) LinkPGN 4,button 5'),
        ('20 21 00 0B 00 91 14 03',
         'If (GPRM11 == SPRM17) LinkPrevC,button 5'),
        ('20 35 00 0D 00 8F 00 63',
         'If (GPRM13 != SPRM15) LinkPTT 99,button 0'),
        ('20 54 00 02 00 02 0D 81',
         'If (GPRM2 > GPRM2) LinkPGCN 3457'),
        ('20 A7 00 03 00 08 0C 43',
         'If (GPRM3 == 8) LinkCN 67,button 3'),
        ('20 C1 00 0E 30 39 5C 07',
         'If (GPRM14 >= 12345) LinkPrevPG,button 23'),
        ('30 02 00 00 00 89 00 00',
         'JumpTT 137'),
        ('30 52 00 00 00 BD 0C 08',
         'If (GPRM12 > GPRM8) JumpTT 189'),
        ('30 62 00 00 00 4E 0C 8F',
         'If (GPRM12 <= SPRM15) JumpTT 78'),
        ('41 00 00 81 83 84 00 00',
         'SetSTN audio=GPRM1, (subpicture=GPRM3):on, angle=GPRM4'),
        ('42 00 00 08 1E D8 00 00',
         'SetNVTMR timer=GPRM8, PGCN=7896'),
        ('43 00 00 07 00 81 00 00',
         'SetGPRMMD counter GPRM1,GPRM7'),
        ('43 60 00 0F 00 89 08 02',
         'If (GPRM8 <= GPRM2) SetGPRMMD counter; GPRM9,GPRM15'),
        ('46 00 00 00 00 0B 00 00',
         'SetHL_BTN button=GPRM11'),
        ('46 40 00 00 00 0C 0A 92',
         'If (GPRM10 >= SPRM18) SetHL_BTN button=GPRM12'),
        ('51 00 00 83 9C 86 00 00',
         'SetSTN audio=4, (subpicture=29):off, angle=6'),
        ('51 00 00 83 DC 86 00 00',
         'SetSTN audio=4, (subpicture=29):on, angle=6'),
        ('51 70 00 83 00 00 06 0F',
         'If (GPRM6 < GPRM15) SetSTN audio=4'),
        ('52 00 00 17 22 3D 00 00',
         'SetNVTMR timer=23, PGCN=8765'),
        ('53 00 62 A4 00 01 00 00',
         'SetGPRMMD register GPRM1,25252'),
        ('53 00 62 A4 00 81 00 00',
         'SetGPRMMD counter GPRM1,25252'),
        ('56 00 00 00 7C 00 00 00',
         'SetHL_BTN button=31'),
        ('63 40 0D 06 00 0A 00 93',
         'If (GPRM13 >= SPRM19) Add GPRM6,GPRM10'),
        ('66 B0 01 0A 00 0E 88 B8',
         'If (GPRM1 != 35000) Div GPRM10,GPRM14'),
        ('71 C0 08 08 00 01 00 0E',
         'If (GPRM8 >= 14) Mov GPRM8,1'),
        ('74 30 00 0B 01 18 00 01',
         'If (GPRM0 != GPRM1) Sub GPRM11,280'),
        ('83 59 00 0C 00 0D 00 07',
         'Add GPRM9,GPRM12; If (GPRM9 > GPRM13) LinkPrevPG,button 0'),
        ('87 97 00 0F B2 6E 38 0C',
         'Mod GPRM7,GPRM15; If (GPRM7 & 45678) LinkGoUpPGC,button 14'),
        ('97 39 00 21 00 90 08 03',
         'Mod GPRM9,33; If (GPRM9 != SPRM16) LinkPrevC,button 2'),
        ('9A A1 00 FF 00 81 24 0A',
         'Or GPRM1,255; If (GPRM1 == 129) LinkNextPGC,button 9'),
        ('A1 28 07 07 00 92 00 00',
         'If (GPRM7 == SPRM18) Mov GPRM8,GPRM7; LinkNoLink,button 0'),
        ('A9 B0 0C 00 00 0F 00 0A',
         'If (GPRM0 != 15) And GPRM0,GPRM12; LinkNextPGC,button 0'),
        ('B1 3A 82 35 0A 8A 4C 0D',
         'If (GPRM10 != SPRM10) Mov GPRM10,33333; LinkTailPGC,button 19'),
        ('C2 5E 0F 0C 00 83 1C 02',
         'If (GPRM12 > SPRM3) Swp GPRM14,GPRM15; LinkNextC,button 7'),
        ('D1 22 00 00 02 80 28 02',
         'If (GPRM2 == SPRM0) Mov GPRM2,0; LinkNextC,button 10'),
        )

    pos = 1
    for (cmdStr, dec) in testCmds:
        print '--> ', dec

        cmd = map(lambda x : int(x,16), string.split(cmdStr))
        d.decodeCommand(cmd, pos)
        print d.getText()
        d.resetText()

        print

        pos += 1

