from dvdread import *
from disassemble import *

def showCommands(set, labels={}):
    global disasm

    for i in range(1, set.count + 1):
        if labels.has_key(i):
            print '          %s:' % labels[i]

        disasm.decodeCommand(set.get(i), i, 12)
        print disasm.getText()
        disasm.resetText()

def showProgramChain(pgc, pgcNr=0):
    print '      Program chain %d' % pgcNr

    print '        %d pre commands:' % pgc.preCommands.count
    showCommands(pgc.preCommands)
    print

    cellLabels = {}
    for i in range(1, pgc.cellCount + 1):
        cmdNr = pgc.getCell(i).commandNr
        if cmdNr != 0:
            cellLabels[cmdNr] = 'cell_%d' % i
    
    print '        %d cell commands (for %d cells):' \
          % (pgc.cellCommands.count, pgc.cellCount)
    showCommands(pgc.cellCommands, cellLabels)
    print
    
    print '        %d post commands:' % pgc.postCommands.count
    showCommands(pgc.postCommands)
    print
    

def listProgramChains(container):
    print '    %d program chain(s)' % container.programChainCount

    for pgcNr in range(1, container.programChainCount + 1):
        pgc = container.getProgramChain(pgcNr)
        showProgramChain(pgc, pgcNr)

def allProgramChains():
    manager = DVDInfo('/dev/dvd').videoManager

    print 'Video Manager:'

    print '  First play:'
    showProgramChain(manager.firstPlay)
    print

    print '  In menu domain:'
    listProgramChains(manager.getLangUnit(1))
    print

    for titleSetNr in range(1, manager.videoTitleSetCount + 1):
        print 'Title Set %d:' % titleSetNr
        titleSet = manager.getVideoTitleSet(titleSetNr)

        print '  In menu domain:'
        listProgramChains(titleSet.getLangUnit(1))
        print

        print '  In video title domain:'
        listProgramChains(titleSet)
        print

disasm = CommandDisassembler()
allProgramChains()
