from dvdread import *

def printTitles(container):
    print '  %d Title(s):' % container.videoTitleCount

    for titleNr in range(1, container.videoTitleCount + 1):
        print '    Title %d:' % titleNr
        title = container.getVideoTitle(titleNr)

        print '      Chapters: %s' % title.chapterCount

def listTitles():
    manager = DVDInfo('/dev/dvd').videoManager

    print 'Video Manager'
    printTitles(manager)
    print

    for titleSetNr in range(1, manager.videoTitleSetCount + 1):
        print 'Title Set %d:' % titleSetNr
        titleSet = manager.getVideoTitleSet(titleSetNr)

        printTitles(titleSet)
        print

def printProgramChains(container):
    print '      %d program chain(s)' % container.programChainCount

    for pgcNr in range(1, container.programChainCount + 1):
        pgc = container.getProgramChain(pgcNr)
        print '        Program chain %d, menu type %d' % (pgcNr, pgc.menuType)
    

def printLangUnits(container):
    print '  %d Language unit(s):' % container.langUnitCount

    for langUnitNr in range(1, container.langUnitCount + 1):
        print '    Language Unit %d:' % langUnitNr
        unit = container.getLangUnit(langUnitNr)

        print '      Language Code: %s (0x%02x%02x)' % \
              (unit.langCode, ord(unit.langCode[0]), ord(unit.langCode[1]))
        printProgramChains(unit)

def listLangUnits():
    manager = DVDInfo('/dev/dvd').videoManager

    print 'Video Manager:'
    printLangUnits(manager)
    print

    for titleSetNr in range(1, manager.videoTitleSetCount + 1):
        print 'Title Set %d:' % titleSetNr
        titleSet = manager.getVideoTitleSet(titleSetNr)

        printLangUnits(titleSet)
        print

