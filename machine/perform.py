import operator
import random

from list import *

def makeNotImplemented(name):
    def reportNotImpl(self, *args):
        raise NotImplementedError, \
              "Operation '%s' not implemented" % name

    return reportNotImpl


#
# Basic Decoding Procedures
#

class CommandPerformer(object):

    #
    # Machine Operations
    #

    # Basic operations.
    nop = makeNotImplemented('nop')
    goto = makeNotImplemented('goto')
    brk = makeNotImplemented('break')
    exit = makeNotImplemented('exit')

    # Parental management

    openSetParentalLevel = makeNotImplemented('openSetParentalLevel')
    closeSetParentalLevel = makeNotImplemented('closeSetParentalLevel')

    # Links.
    linkTopCell = makeNotImplemented('linkTopCell')
    linkNextCell = makeNotImplemented('linkNextCell')
    linkPrevCell = makeNotImplemented('linkPrevCell')
    linkTopProgram = makeNotImplemented('linkTopProgram')
    linkNextProgram = makeNotImplemented('linkNextProgram')
    linkPrevProgram = makeNotImplemented('linkPrevProgram')
    linkTopProgramChain = makeNotImplemented('linkTopProgramChain')
    linkNextProgramChain = makeNotImplemented('linkNextProgramChain')
    linkPrevProgramChain = makeNotImplemented('linkPrevProgramChain')
    linkGoUpProgramChain = makeNotImplemented('linkGoUpProgramChain')
    linkTailProgramChain = makeNotImplemented('linkTailProgramChain')
    linkProgramChain = makeNotImplemented('linkProgramChain')
    linkChapter = makeNotImplemented('linkChapter')
    linkProgram = makeNotImplemented('linkProgram')
    linkCell = makeNotImplemented('linkCell')

    # Select (highlight) a button
    selectButton = makeNotImplemented('selectButton')

    # Jumps
    jumpToTitle = makeNotImplemented('jumpToTitle')
    jumpToTitleInSet = makeNotImplemented('jumpToTitleInSet')
    jumpToChapterInSet = makeNotImplemented('jumpToChapterInSet')

    jumpToFirstPlay = makeNotImplemented('jumpToFirstPlay')
    jumpToTitleMenu = makeNotImplemented('jumpToTitleMenu')
    jumpToMenu = makeNotImplemented('jumpToMenu')
    jumpToManagerProgramChain = \
        makeNotImplemented('jumpToManagerProgramChain')

    # Timed jump
    setTimedJump = makeNotImplemented('setTimedJump')

    # Call and resume
    callFirstPlay = makeNotImplemented('callFirstPlay')
    callTitleMenu = makeNotImplemented('callTitleMenu')
    callMenu = makeNotImplemented('callMenu')
    callManagerProgramChain = makeNotImplemented('callManagerProgramChain')
    resume = makeNotImplemented('resume')

    # Selectable streams
    setAngle = makeNotImplemented('setAngle')
    setAudio = makeNotImplemented('setAudio')
    setSubpicture = makeNotImplemented('setSubpicture')

    # Karaoke control
    setKaraokeMode = makeNotImplemented('setKaraokeMode')


    #
    # Registers
    #

    class Register(object):
        getValue = makeNotImplemented('Register.getValue')
        setValue = makeNotImplemented('Register.setValue')

    dummyRegister = Register()

    def getGeneralPurpose(self, regNr):
        assert 0 <= regNr <= 15
        return self.dummyRegister

    def getSystemParameter(self, regNr):
        assert 0 <= regNr <= 23
        return self.dummyRegister

    def getRegister(self, regNr):
        if regNr & 0x80:
            return self.getSystemParameter(regNr & 0x7f)
        else:
            return self.getGeneralPurpose(regNr)


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
            op1 = self.getGeneralPurpose(cmd[1] & 0xf).getValue()
        else:
            op1 = self.getGeneralPurpose(cmd[pos1]).getValue()

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
        pass


    #
    # Link Operations
    #

    simpleLinkOpNames = {
        0x01: 'linkTopCell',
        0x02: 'linkNextCell',
        0x03: 'linkPrevCell',
        0x05: 'linkTopProgram',
        0x06: 'linkNextProgram',
        0x07: 'linkPrevProgram',
        0x09: 'linkTopProgramChain',
        0x0a: 'linkNextProgramChain',
        0x0b: 'linkPrevProgramChain',
        0x0c: 'linkGoUpProgramChain',
        0x0d: 'linkTailProgramChain',
        0x10: 'resume'}

    def performLink(self, cmd):
        if 0x8 <= cmd[0] >> 4 <= 0xd:
            # Commands in this range are limited to simple links.
            linkType = 1
        else:
            linkType = cmd[1] & 0xf

        if linkType == 0x0:
            return
        elif linkType == 0x1:
            # Call by name to allow for operation redefinition.
            try:
                methodName = self.simpleLinkOpNames[cmd[7]]
            except KeyError:
                return
            getattr(self, methodName)()
            self.performButton(cmd)
        elif linkType == 0x4:
            self.linkProgramChain(cmd[6] * 0x100 + cmd[7])
        elif linkType == 0x5:
            self.linkChapter((cmd[6] & 0x3) * 0x100 + cmd[7])
            self.performButton(cmd)
        elif linkType == 0x6:
            self.linkProgram(cmd[7])
            self.performButton(cmd)
        elif linkType == 0x7:
            self.linkCell(cmd[7])
            self.performButton(cmd)
        else:
            assert False, 'Unknown link operation'

    def performButton(self, cmd):
        # Handle the select button operation.
        button = cmd[6] >> 2
        if button != 0:
            self.selectButton(button)


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

        dest = self.getGeneralPurpose(regNr)
        if op == 2:
            # Perform a register swap.
            assert isinstance(source, self.Register)
            tmp = dest.getValue()
            dest.setValue(source.getValue())
            source.setValue(tmp)
        else:
            opFunc = self.arithOps[op]

            if isinstance(source, self.Register):
                value = source.getValue()
            else:
                value = source

            dest.setValue(opFunc(dest.getValue(), value))


    #
    # Command Perform Functions
    #

    def perform0(self, cmd):
        if not self.openCondition(cmd):
            return

        op = cmd[1] & 0xf
        if op == 0:
            self.nop()
        elif op == 1:
            self.goto(cmd[7])
        elif op == 2:
            self.brk()
        elif op == 3:
            if self.openSetParentalLevel(cmd):
                self.goto(cmd[7])
                self.closeSetParentalLevel(cmd)

        self.closeCondition(cmd)

    def perform2(self, cmd):
        if not self.openCondition(cmd):
            return

        self.performLink(cmd)

        self.closeCondition(cmd)

    def perform3(self, cmd):
        if not self.openCondition(cmd):
            return

        op = cmd[1] & 0xf
        if op == 1:
            self.exit()
        elif op == 2:
            self.jumpToTitle(cmd[5])
        elif op == 3:
            self.jumpToTitleInSet(cmd[5])
        elif op == 5:
            self.jumpToChapterInSet(cmd[5], cmd[2] * 0x100 + cmd[3])
        elif op == 6:
            subop = cmd[5] >> 4
            if subop == 0x0:
                self.jumpToFirstPlay()
            elif subop == 0x4:
                self.jumpToTitleMenu()
            elif subop == 0x8:
                # Ignore the title, menus belong to the titleset anyway.
                self.jumpToMenu(cmd[4], cmd[5] & 0xf)
            elif subop == 0xc:
                self.jumpToManagerProgramChain(cmd[2] * 0x100 + cmd[3])
            else:
                assert False, 'Jump supoberation unknown'
        elif op == 8:
            subop = cmd[5] >> 4
            if subop == 0x0:
                self.callFirstPlay(cmd[4])
            elif subop == 0x4:
                self.callTitleMenu(cmd[4])
            elif subop == 0x8:
                self.callMenu(cmd[5] & 0xf, cmd[4])
            elif subop == 0xc:
                self.callManagerProgramChain(cmd[2] * 0x100 + cmd[3], cmd[4])
            else:
                assert False, 'Jump supoberation unknown'
        else:
            assert False, 'Unknown jump/call operation'
        
        self.closeCondition(cmd)

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
                self.setAudio(getParm(cmd[3] & 0x7f))
            if cmd[4] & 0x80:
                self.setSubpicture(getParm(cmd[4] & 0x7f))
            if cmd[5] & 0x80:
                self.setAngle(getParm(cmd[5] & 0x7f))
        elif op == 2:
            self.setTimedJump(cmd[4] * 0x100 + cmd[5], getParm(cmd[3]))
        elif op == 3:
            regNr = cmd[5] & 0xf
            value = getParm(cmd[2] * 0x100 + cmd[3])
            if cmd[5] & 0x80:
                self.getGeneralPurpose(regNr).setValue(value, True)
            else:
                self.getGeneralPurpose(regNr).setValue(value)
        elif op == 4:
            self.setKaraokeMode(getParm(cmd[4] * 0x100 + cmd[5]))
        elif op == 6:
            self.getSystemParameter(8). \
                setValue(getParm(cmd[4] * 0x100 + cmd[5]))
        else:
            assert False, 'Unknown SRPM set operation'

        self.performLink(cmd)

        self.closeCondition(cmd)

    def perform6(self, cmd):
        assert cmd[1] & 0xf0 == 0 or cmd[1] & 0xf == 0

        if not self.openCondition(cmd):
            return

        self.performArithOperation(cmd, cmd[3],
                                   self.getRegister(cmd[5]))
        self.performLink(cmd)

        self.closeCondition(cmd)

    def perform7(self, cmd):
        assert cmd[1] & 0xf0 == 0 or cmd[1] & 0xf == 0

        if not self.openCondition(cmd):
            return

        self.performArithOperation(cmd, cmd[3], cmd[4] * 0x100 + cmd[5])
        self.performLink(cmd)

        self.closeCondition(cmd)

    def perform8(self, cmd):
        self.performArithOperation(cmd, cmd[1] & 0xf,
                                   self.getRegister(cmd[3]))
        
        if not self.openCondition(cmd):
            return

        self.performLink(cmd)

        self.closeCondition(cmd)

    def perform9(self, cmd):
        self.performArithOperation(cmd, cmd[1] & 0xf,
                                   cmd[2] * 0x100 + cmd[3])
        
        if not self.openCondition(cmd):
            return

        self.performLink(cmd)

        self.closeCondition(cmd)

    def performA(self, cmd):
        if not self.openCondition(cmd):
            return

        self.performArithOperation(cmd, cmd[1] & 0xf,
                                   self.getRegister(cmd[2]))
        self.performLink(cmd)

        self.closeCondition(cmd)

    def performB(self, cmd):
        if not self.openCondition(cmd):
            return

        self.performArithOperation(cmd, cmd[1] & 0xf,
                                   cmd[2] * 0x100 + cmd[3])
        self.performLink(cmd)

        self.closeCondition(cmd)

    def performC(self, cmd):
        if self.openCondition(cmd):
            self.performArithOperation(cmd, cmd[1] & 0xf,
                                       self.getRegister(cmd[2]))
            self.closeCondition(cmd)

        self.performLink(cmd)

    def performD(self, cmd):
        if self.openCondition(cmd):
            self.performArithOperation(cmd, cmd[1] & 0xf,
                                       cmd[2] * 0x100 + cmd[3])
            self.closeCondition(cmd)

        self.performLink(cmd)


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
        self.performFuncs[cmd[0] >> 4](self, cmd)
