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

import operator
import random

from itersched import *


class Register(object):
    """A base class for all register types.

    Implementations of the machine interface must use this class as
    base class for all objects returned as registers."""

    __slots__ = ()


class CommandDecoder(object):
    """A decoder for DVD virtual machine commands."""

    __slots__ = ('machine',)


    def __init__(self, machine):
        """Creates a new CommandDecoder that uses the specified
        virtual machine to execute the commands."""
        self.machine = machine


    #
    # Registers
    #
    
    def getRegister(self, regNr):
        if regNr & 0x80:
            return self.machine.getSystemParameter(regNr & 0x7f)
        else:
            return self.machine.getGeneralPurpose(regNr)


    #
    # Conditions
    #

    def makeCondOperation(operator):
        def evalCond(self, op1, op2):
            return operator(op1, op2)

        return evalCond

    conditions = (
        None,
        makeCondOperation(operator.__and__),
        makeCondOperation(operator.eq),
        makeCondOperation(operator.ne),
        makeCondOperation(operator.ge),
        makeCondOperation(operator.gt),
        makeCondOperation(operator.le),
        makeCondOperation(operator.lt)
        )


    condOperands = (
        (3, 4, True),
        None,
        (3, 4, True),
        (6, 7, False),
        (6, 7, False),
        (6, 7, False),
        (2, 6, True),
        (2, 6, True),
        (1, 4, True),
        (1, 4, True),
        (3, 4, True),
        (4, 5, False),
        (3, 4, True),
        (4, 5, False),
        None,
        None)

    def openCondition(self, cmd):
        cond = self.conditions[(cmd[1] >> 4) & 0x7]
        if cond == None:
            # No condition
            return True

        # Get the first operand, which is always the value of a register.
        (pos1, pos2, dbl) = self.condOperands[cmd[0] >> 4]
        if pos1 == 1:
            # Special case, we are interested in the second nibble of byte 1.
            op1 = self.machine.getGeneralPurpose(cmd[1] & 0xf).getValue()
        else:
            op1 = self.machine.getGeneralPurpose(cmd[pos1]).getValue()

        # Get the second operand. It could be the value of a register
        # or a constant.
        if cmd[1] & 0x80:
            # We have a direct operand (a constant).
            assert dbl, "Operation allows no direct condition operand"
            op2 = cmd[pos2] * 0x100 + cmd[pos2 + 1]
        else:
            # We have a register operand.
            if dbl:
                assert cmd[pos2] == 0
                regNr = cmd[pos2 + 1]
            else:
                regNr = cmd[pos2]

            op2 = self.getRegister(regNr).getValue()

        # Perform the condition.
        return cond(self, op1, op2)

    def closeCondition(self, cmd):
        yield NoOp


    #
    # Link Operations
    #

    def performLink(self, cmd):
        if 0x8 <= cmd[0] >> 4 <= 0xd:
            # Commands in this range are limited to simple links.
            linkType = 1
        else:
            linkType = cmd[1] & 0xf

        if linkType == 0x0:
            return
        elif linkType == 0x1:
            yield Call(self.performButton(cmd))

            if cmd[7] == 0x01:
                yield Call(self.machine.linkTopCell())
            elif cmd[7] == 0x02:
                yield Call(self.machine.linkNextCell())
            elif cmd[7] == 0x03:
                yield Call(self.machine.linkPrevCell())
            elif cmd[7] == 0x05:
                yield Call(self.machine.linkTopProgram())
            elif cmd[7] == 0x06:
                yield Call(self.machine.linkNextProgram())
            elif cmd[7] == 0x07:
                yield Call(self.machine.linkPrevProgram())
            elif cmd[7] == 0x09:
                yield Call(self.machine.linkTopProgramChain())
            elif cmd[7] == 0x0a:
                yield Call(self.machine.linkNextProgramChain())
            elif cmd[7] == 0x0b:
                yield Call(self.machine.linkPrevProgramChain())
            elif cmd[7] == 0x0c:
                yield Call(self.machine.linkGoUpProgramChain())
            elif cmd[7] == 0x0d:
                yield Call(self.machine.linkTailProgramChain())
            elif cmd[7] == 0x10:
                yield Call(self.machine.resume())
        elif linkType == 0x4:
            yield Call(self.machine.linkProgramChain(cmd[6] * \
                                                     0x100 + cmd[7]))
        elif linkType == 0x5:
            yield Call(self.performButton(cmd))
            yield Call(self.machine.linkChapter((cmd[6] & 0x3) * \
                                                0x100 + cmd[7]))
        elif linkType == 0x6:
            yield Call(self.performButton(cmd))
            yield Call(self.machine.linkProgram(cmd[7]))
        elif linkType == 0x7:
            yield Call(self.performButton(cmd))
            yield Call(self.machine.linkCell(cmd[7]))
        else:
            assert False, 'Unknown link operation'

    def performButton(self, cmd):
        # Handle the select button operation.
        button = cmd[6] >> 2
        if button != 0:
            yield Call(self.machine.selectButton(button))


    #
    # Arithmetic and Bit Operations
    #

    arithOps = (
        None,
        lambda x, y: y,
	None,		# Swap is a special case.
	operator.add,
	operator.sub,
	operator.mul,
	operator.div,
	operator.mod,
        lambda x, y: random.randint(1, y),
	operator.__and__,
	operator.__or__,
	operator.__xor__,
        None,
        None,
        None,
        None)

    def performArithOperation(self, cmd, regNr, source):
        op = cmd[0] & 0xf
        if op == 0:
            return

        dest = self.machine.getGeneralPurpose(regNr)
        if op == 2:
            # Perform a register swap.
            assert isinstance(source, Register)
            tmp = dest.getValue()
            yield Call(dest.setValue(source.getValue()))
            yield Call(source.setValue(tmp))
        else:
            opFunc = self.arithOps[op]

            if isinstance(source, Register):
                value = source.getValue()
            else:
                value = source

            yield Call(dest.setValue(opFunc(dest.getValue(), value)))


    #
    # Command Perform Functions
    #

    def perform0(self, cmd):
        if not self.openCondition(cmd):
            return

        op = cmd[1] & 0xf
        if op == 0:
            yield Call(self.machine.nop())
        elif op == 1:
            yield Call(self.machine.goto(cmd[7]))
        elif op == 2:
            yield Call(self.machine.brk())
        elif op == 3:
            if self.machine.openSetParentalLevel(cmd):
                yield Call(self.machine.goto(cmd[7]))
                yield Call(self.machine.closeSetParentalLevel(cmd))

        yield Call(self.closeCondition(cmd))

    def perform2(self, cmd):
        if not self.openCondition(cmd):
            return

        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def perform3(self, cmd):
        if not self.openCondition(cmd):
            return

        op = cmd[1] & 0xf
        if op == 1:
            yield Call(self.machine.exit())
        elif op == 2:
            yield Call(self.machine.jumpToTitle(cmd[5]))
        elif op == 3:
            yield Call(self.machine.jumpToTitleInSet(cmd[5]))
        elif op == 5:
            yield Call(self.machine.jumpToChapterInSet(cmd[5], cmd[2] * \
                                                       0x100 + cmd[3]))
        elif op == 6:
            subop = cmd[5] >> 4
            if subop == 0x0:
                yield Call(self.machine.jumpToFirstPlay())
            elif subop == 0x4:
                yield Call(self.machine.jumpToTitleMenu())
            elif subop == 0x8:
                yield Call(self.machine.jumpToMenu(cmd[4], cmd[3],
                                                   cmd[5] & 0xf))
            elif subop == 0xc:
                yield Call(self.machine. \
                           jumpToManagerProgramChain(cmd[2] * 0x100 + cmd[3]))
            else:
                assert False, 'Jump suboperation unknown'
        elif op == 8:
            subop = cmd[5] >> 4
            if subop == 0x0:
                yield Call(self.machine.callFirstPlay(cmd[4]))
            elif subop == 0x4:
                yield Call(self.machine.callTitleMenu(cmd[4]))
            elif subop == 0x8:
                yield Call(self.machine.callMenu(cmd[5] & 0xf, cmd[4]))
            elif subop == 0xc:
                yield Call(self.machine. \
                           callManagerProgramChain(cmd[2] * 0x100
                                                   + cmd[3], cmd[4]))
            else:
                assert False, 'Jump suboperation unknown'
        else:
            assert False, 'Unknown jump/call operation'
        
        yield Call(self.closeCondition(cmd))

    def perform45(self, cmd):
        assert cmd[1] & 0xf0 == 0 or cmd[1] & 0xf == 0

        if not self.openCondition(cmd):
            return

        if (cmd[0] & 0xf0) == 0x40:
            # Indirect access to the parameters.
            getParm = lambda regNr, self=self: \
                      self.getRegister(regNr).getValue()
        else:
            # Direct access to the parameters.
            getParm = lambda x: x

        op = cmd[0] & 0xf
        if op == 1:
            if cmd[3] & 0x80:
                yield Call(self.machine.setAudio(getParm(cmd[3] & 0x7f)))
            if cmd[4] & 0x80:
                yield Call(self.machine.setSubpicture(getParm(cmd[4] & 0x7f)))
            if cmd[5] & 0x80:
                yield Call(self.machine.setAngle(getParm(cmd[5] & 0x7f)))
        elif op == 2:
            yield Call(self.machine.setTimedJump(cmd[4] * 0x100 + cmd[5],
                                                 getParm(cmd[3])))
        elif op == 3:
            regNr = cmd[5] & 0xf
            value = getParm(cmd[2] * 0x100 + cmd[3])
            if cmd[5] & 0x80:
                yield Call(self.machine.getGeneralPurpose(regNr). \
                           setValue(value, True))
            else:
                yield Call(self.machine.getGeneralPurpose(regNr). \
                           setValue(value))
        elif op == 4:
            yield Call(self.machine.setKaraokeMode(getParm(cmd[4] * \
                                                           0x100 + cmd[5])))
        elif op == 6:
            yield Call(self.machine.setSystemParam8(getParm(cmd[4] * \
                                                            0x100 + cmd[5])))
        else:
            assert False, 'Unknown SRPM set operation'

        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def perform6(self, cmd):
        assert cmd[1] & 0xf0 == 0 or cmd[1] & 0xf == 0

        if not self.openCondition(cmd):
            return

        yield Call(self.performArithOperation(cmd, cmd[3],
                                              self.getRegister(cmd[5])))
        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def perform7(self, cmd):
        assert cmd[1] & 0xf0 == 0 or cmd[1] & 0xf == 0

        if not self.openCondition(cmd):
            return

        yield Call(self.performArithOperation(cmd, cmd[3],
                                              cmd[4] * 0x100 + cmd[5]))
        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def perform8(self, cmd):
        yield Call(self.performArithOperation(cmd, cmd[1] & 0xf,
                                              self.getRegister(cmd[3])))
        
        if not self.openCondition(cmd):
            return

        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def perform9(self, cmd):
        yield Call(self.performArithOperation(cmd, cmd[1] & 0xf,
                                              cmd[2] * 0x100 + cmd[3]))
        
        if not self.openCondition(cmd):
            return

        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def performA(self, cmd):
        if not self.openCondition(cmd):
            return

        yield Call(self.performArithOperation(cmd, cmd[1] & 0xf,
                                              self.getRegister(cmd[2])))
        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def performB(self, cmd):
        if not self.openCondition(cmd):
            return

        yield Call(self.performArithOperation(cmd, cmd[1] & 0xf,
                                              cmd[2] * 0x100 + cmd[3]))
        yield Call(self.performLink(cmd))

        yield Call(self.closeCondition(cmd))

    def performC(self, cmd):
        if self.openCondition(cmd):
            yield Call(self.performArithOperation(cmd, cmd[1] & 0xf,
                                                  self.getRegister(cmd[2])))
            yield Call(self.closeCondition(cmd))

        yield Call(self.performLink(cmd))

    def performD(self, cmd):
        if self.openCondition(cmd):
            yield Call(self.performArithOperation(cmd, cmd[1] & 0xf,
                                                  cmd[2] * 0x100 + cmd[3]))
            yield Call(self.closeCondition(cmd))

        yield Call(self.performLink(cmd))


    performFuncs = (
        perform0,
        None,
        perform2,
        perform3,
        perform45,
        perform45,
        perform6,
        perform7,
        perform8,
        perform9,
        performA,
        performB,
        performC,
        performD,
        None,
        None)


    #
    # Main Entry Point
    #

    def performCommand(self, cmd):
        yield Call(self.performFuncs[cmd[0] >> 4](self, cmd))
