# Seamless DVD Player
# Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
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

import string

from perform import *


class IndentedText(object):
    def __init__(self):
        self.indentLevel = 0
        self.lines = []

    def openIndent(self, spcCount = 2):
        self.indentLevel += spcCount

    def closeIndent(self, spcCount = 2):
        self.indentLevel -= spcCount

    def append(self, text):
        spcs = " " * self.indentLevel
        self.lines.extend(map(lambda x: spcs + x, string.split(text, '\n')))

    def appendToLine(self, text):
        if self.lines == []:
            self.lines = [text]
        else:
            self.lines[-1] += text

    def getText(self):
        return string.join(self.lines, '\n')

    __repr__ = getText


class CommandDisassembler(CommandPerformer):
    def __init__(self):
        self.resetText()


    #
    # Text Handling 
    #

    def resetText(self):
        self.text = IndentedText()

    def getText(self):
        return self.text.getText()


    #
    # Machine Operations
    #

    def makeMachineOperation(format):
        def printOp(self, *args):
            self.text.append(format % tuple(map(str, args)))

        return printOp

    # Basic operations.
    nop = makeMachineOperation('nop()')
    goto = makeMachineOperation('goto(%s)')
    brk = makeMachineOperation('break()')
    exit = makeMachineOperation('exit()')

    # Parental management

    def openSetParentalLevel(self, cmd):
        self.text.append('if setTmpPML(%s):' % (cmd[6] & 0xf))
        self.text.openIndent()

        # When decoding to text, we need the condition 'body' to
        # be decoded anyway.
        return True

    def closeSetParentalLevel(self, cmd):
        self.text.closeIndent()

    # Links.
    linkTopCell = makeMachineOperation('linkTopCell()')
    linkNextCell = makeMachineOperation('linkNextCell()')
    linkPrevCell = makeMachineOperation('linkPrevCell()')
    linkTopProgram = makeMachineOperation('linkTopProgram()')
    linkNextProgram = makeMachineOperation('linkNextProgram()')
    linkPrevProgram = makeMachineOperation('linkPrevProgram()')
    linkTopProgramChain = makeMachineOperation('linkTopProgramChain()')
    linkNextProgramChain = makeMachineOperation('linkNextProgramChain()')
    linkPrevProgramChain = makeMachineOperation('linkPrevProgramChain()')
    linkGoUpProgramChain = makeMachineOperation('linkGoUpProgramChain()')
    linkTailProgramChain = makeMachineOperation('linkTailProgramChain()')
    linkProgramChain = makeMachineOperation('linkProgramChain(%s)')
    linkChapter = makeMachineOperation('linkChapter(%s)')
    linkProgram = makeMachineOperation('linkProgram(%s)')
    linkCell = makeMachineOperation('linkCell(%s)')

    # Select (highlight) a button
    selectButton = makeMachineOperation('selectButton(%s)')
    setSystemParam8 = makeMachineOperation('selectButton(%s >> 10)')

    # Jumps
    jumpToTitle = makeMachineOperation('jumpToTitle(%s)')
    jumpToTitleInSet = makeMachineOperation('jumpToTitleInSet(%s)')
    jumpToChapterInSet = \
        makeMachineOperation('jumpToChapterInSet(title=%s, chapter=%s)')

    jumpToFirstPlay = makeMachineOperation('jumpToFirstPlay()')
    jumpToTitleMenu = makeMachineOperation('jumpToTitleMenu()')
    jumpToMenu = makeMachineOperation('jumpToMenu(titleSetNr=%s, ' \
                                      'titleNr=%s, menu=%s)')
    jumpToManagerProgramChain = \
        makeMachineOperation('jumpToManagerProgramChain(%s)')

    # Timed jump
    setTimedJump = \
        makeMachineOperation('setTimedJump(programChain=%s, time=%s)')

    # Call and resume
    callFirstPlay = makeMachineOperation('callFirstPlay(return=%s)')
    callTitleMenu = makeMachineOperation('callTitleMenu(return=%s)')
    callMenu = makeMachineOperation('callMenu(menu=%s, return=%s)')
    callManagerProgramChain = \
        makeMachineOperation('callManagerProgramChain(programChain=%s, '
                             'return=%s)')
    resume = makeMachineOperation('resume()')

    # Selectable streams
    setAngle = makeMachineOperation('setAngle(%s)')
    setAudio = makeMachineOperation('setAudio(%s)')
    setSubpicture = makeMachineOperation('setSubpicture(%s)')

    # Karaoke control
    setKaraokeMode = makeMachineOperation('setKaraokeMode(0x%x)')


    #
    # Registers
    #

    class Register(CommandPerformer.Register):
        def __init__(self, parent, name):
            self.parent = parent
            self.name = name

        def setValue(self, value, counter=False):
            if counter:
                self.parent.text.append('counter %s = %s' % (self.name, value))
            else:
                self.parent.text.append('%s = %s' % (self.name, value))

        def getValue(self):
            return self.name

        __str__ = getValue


    def getGeneralPurpose(self, regNr):
        assert 0 <= regNr <= 15
        return self.Register(self, 'gprm%d' % regNr)

    systemParameterNames = (
        'sprm0_menu_language',
        'sprm1_audio_stream',
        'sprm2_subpicture_stream',
        'sprm3_angle',
        'sprm4_title_in_volume',
        'sprm5_title_in_vts',
        'sprm6_program_chain',
        'sprm7_chapter',
        'sprm8_highlighted_button',
        'sprm9_navigation_timer',
        'sprm10_program_chain_for_timer',
        'sprm11_karaoke_mode',
        'sprm12_parental_country',
        'sprm13_parental_level',
        'sprm14_video_mode_pref',
        'sprm15_audio_caps',
        'sprm16_audio_lang_pref',
        'sprm17_audio_ext_pref',
        'sprm18_subpicture_lang_pref',
        'sprm19_subpicture_ext_pref',
        'sprm20_region_code',
        'sprm21_reserved',
        'sprm22_reserved',
        'sprm23_reserved_ext_playback')

    def getSystemParameter(self, regNr):
        assert 0 <= regNr <= 23
        return self.Register(self, self.systemParameterNames[regNr])


    #
    # Conditions
    #

    def makeCondOperation(operator):
        def printCond(self, op1, op2):
            self.text.append("if %s %s %s:" % (str(op1), operator, str(op2)))
            self.text.openIndent()

            # When decoding to text, we need the condition 'body' to
            # be decoded anyway.
            return True

        return printCond

    conditions = (
        None,
        makeCondOperation('&'),
        makeCondOperation('=='),
        makeCondOperation('!='),
        makeCondOperation('>='),
        makeCondOperation('>'),
        makeCondOperation('<='),
        makeCondOperation('<'))

    def closeCondition(self, cmd):
        if cmd[1] & 0x70 == 0:
            return 

        self.text.closeIndent()


    #
    # Arithmetic and Bit Operations
    #

    arithOpsStrs = (
        None,
	'%s = %s',
	'swap(%s, %s)',
	'%s += %s',
	'%s -= %s',
	'%s *= %s',
	'%s /= %s',
	'%s %%= %s',
	'%s = random(%s)',
	'%s &= %s',
	'%s |= %s',
	'%s ^= %s',
        None,
        None,
        None,
        None)

    def performArithOperation(self, cmd, regNr, operand):
        opStr = self.arithOpsStrs[cmd[0] & 0xf]
        self.text.append(opStr % \
                         (str(self.getGeneralPurpose(regNr)), str(operand)))


    #
    # Entry Point
    #

    def decodeCommand(self, cmd, pos=0, indent=0):
        self.text.openIndent(indent)

        self.text.append("%03d:" % pos)
        for i in range(8):
            self.text.appendToLine(" %02x" % cmd[i])

        self.text.openIndent(5)

        self.performCommand(cmd)

        self.text.closeIndent(5)

        self.text.closeIndent(indent)
