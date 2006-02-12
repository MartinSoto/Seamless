# -*- Pyrex -*-
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


import time

cdef extern from "Python.h":
    int PyObject_AsReadBuffer(object obj,
                              char **buffer,
                              int *buffer_len)

    object PyString_FromStringAndSize(char *v, int len)


#
# IFO File Support
#

cdef extern from "dvdread/dvd_reader.h":
    enum dvd_read_domain_t:
        DVD_READ_INFO_FILE,
        DVD_READ_INFO_BACKUP_FILE,
        DVD_READ_MENU_VOBS,
        DVD_READ_TITLE_VOBS

    struct dvd_reader_s
    ctypedef dvd_reader_s dvd_reader_t

    struct dvd_file_s
    ctypedef dvd_file_s dvd_file_t

    dvd_reader_t *DVDOpen(char *path)
    void DVDClose(dvd_reader_t * dvd)

include "ifo_types.pyx"

cdef extern from "dvdread/ifo_print.h":
    void ifoPrint(dvd_reader_t *dvd, int title)

cdef extern from "dvdread/ifo_read.h":
    ifo_handle_t* ifoOpen(dvd_reader_t *dvd, int title)
    void ifoClose(ifo_handle_t *ifoFile)


# The dvd_read_domain_t enumeration.
DOMAIN_INFO_FILE = DVD_READ_INFO_FILE
DOMAIN_INFO_BACKUP_FILE = DVD_READ_INFO_BACKUP_FILE
DOMAIN_MENU = DVD_READ_MENU_VOBS
DOMAIN_TITLE = DVD_READ_TITLE_VOBS


# Menu types
MENU_TYPE_TITLE = 2
MENU_TYPE_ROOT = 3
MENU_TYPE_SUBPICTURE = 4
MENU_TYPE_AUDIO = 5
MENU_TYPE_ANGLE = 6
MENU_TYPE_CHAPTER = 7


# Interval Ids for the DSI packages.
INTERVAL_120 = 0
INTERVAL_60 = 1
INTERVAL_30 = 2
INTERVAL_10 = 3
INTERVAL_7_5 = 4
INTERVAL_7_0 = 5
INTERVAL_6_5 = 6
INTERVAL_6_0 = 7
INTERVAL_5_5 = 8
INTERVAL_5_0 = 9
INTERVAL_4_5 = 10
INTERVAL_4_0 = 11
INTERVAL_3_5 = 12
INTERVAL_3_0 = 13
INTERVAL_2_5 = 14
INTERVAL_2_0 = 15
INTERVAL_1_5 = 16
INTERVAL_1_0 = 17
INTERVAL_0_5 = 18


# Known supported audio formats
AUDIO_FORMAT_AC3 = 0
AUDIO_FORMAT_UNKNOWN1 = 1
AUDIO_FORMAT_MPEG1 = 2
AUDIO_FORMAT_MPEG2EXT = 3
AUDIO_FORMAT_LPCM = 4
AUDIO_FORMAT_UNKNOWN2 = 5
AUDIO_FORMAT_DTS = 6
AUDIO_FORMAT_UNKNOWN3 = 7


# Known supported subpicture formats
SUBPICTURE_FORMAT_RUNLENGTH = 0
SUBPICTURE_FORMAT_EXTENDED = 1
SUBPICTURE_FORMAT_OTHER = 2


# Aspect ratios.
ASPECT_RATIO_4_3 = 0
ASPECT_RATIO_NOT_SPECIFIED = 1
ASPECT_RATIO_RESERVED = 2
ASPECT_RATIO_16_9 = 3


# Video modes.
VIDEO_MODE_NORMAL = 0
VIDEO_MODE_PAN_SCAN = 1
VIDEO_MODE_LETTERBOX = 2
VIDEO_MODE_RESERVED = 3


# Highlight status values.
HLSTATUS_NONE = 0		# No highlight info.
HLSTATUS_NEW_INFO = 1		# New highlight info.
HLSTATUS_PREVIOUS = 2		# Equal to previous nav packet.
HLSTATUS_PREVIOUS_CMDS = 3	# Equal to previous nav except for commands.


# Video standards.
VIDEO_STD_NTSC = 0
VIDEO_STD_PAL = 1


# PAL film mode.
PAL_FILM_MODE_CAMERA = 0
PAL_FILM_MODE_FIML = 1


# Compression types.
COMPRESSION_TYPE_VARIABLE = 0
COMPRESSION_TYPE_CONSTANT = 1


# Subpicture physical stream types.
SUBPICTURE_PHYS_TYPE_4_3 = 0
SUBPICTURE_PHYS_TYPE_WIDESCREEN = 1
SUBPICTURE_PHYS_TYPE_LETTERBOX = 2
SUBPICTURE_PHYS_TYPE_PAN_SCAN = 3


# Cell block modes.
CELL_BLOCK_MODE_NORMAL = 0
CELL_BLOCK_MODE_ANGLE_FIRST = 1
CELL_BLOCK_MODE_ANGLE_MIDDLE = 2
CELL_BLOCK_MODE_ANGLE_LAST = 3


# Cell block types.
CELL_BLOCK_TYPE_NORMAL = 0
CELL_BLOCK_TYPE_ANGLE = 1


cdef class Time
cdef class Cell
cdef class ProgramChain
cdef class LangUnit
cdef class Chapter
cdef class VideoTitle
cdef class VideoTitleSet
cdef class VideoManager
cdef class DVDInfo


cdef int extractBCD(uint8_t bcd):
    return (bcd >> 4) * 10 + (bcd & 0xf)

cdef object langCodeToString(uint16_t langCode):
    return chr(langCode >> 8) + chr(langCode & 0xff)


class DVDReadError(Exception):
    pass


cdef class Time:
    cdef dvd_time_t *time

    property hour:
        def __get__(self):
            return extractBCD(self.time.hour)

    property minute:
        def __get__(self):
            return extractBCD(self.time.minute)

    property second:
        def __get__(self):
            return extractBCD(self.time.second)

    property frame:
        def __get__(self):
            return extractBCD(self.time.frame_u &0x3f)

    property frameRate:
        def __get__(self):
            if self.time.frame_u >> 6 == 0x3:
                return 30
            elif self.time.frame_u >> 6 == 0x1:
                return 25
            else:
                return None

    property seconds:
        def __get__(self):
            return (self.hour * 60.0 + self.minute) * 60.0 + \
                   self.second + float(self.frame) / self.frameRate

    def __repr__(self):
        return "%02x:%02x:%02x + %02x frames at %02d fps" % \
               (self.time.hour, self.time.minute, self.time.second,
                self.time.frame_u & 0x3f, self.frameRate)

cdef Time wrapTime(dvd_time_t *time):
    cdef Time new

    new = Time()
    new.time = time
    return new


cdef wrapCommand(vm_cmd_t *cmd):
    return (cmd.bytes[0], cmd.bytes[1], cmd.bytes[2], cmd.bytes[3],
            cmd.bytes[4], cmd.bytes[5], cmd.bytes[6], cmd.bytes[7])


cdef class CommandSet:
    cdef vm_cmd_t *commands
    cdef readonly int count

    def get(self, int commandNr):
        if not 1 <= commandNr <= self.count:
            raise IndexError, "command number out of range"

        return wrapCommand(self.commands + (commandNr - 1))

cdef wrapCommandSet(vm_cmd_t *commands, int count):
    cdef CommandSet set

    set = CommandSet()
    set.commands = commands
    set.count = count

    return set


cdef class Cell:
    cdef readonly ProgramChain programChain

    cdef cell_playback_t *cell
    cdef cell_position_t *cellPos

    cdef readonly int cellNr	# Cell number in program chain.
    cdef readonly float startSeconds
    				# Start time in seconds from the
                                # beginning of the program chain.

    def __new__(self, ProgramChain programChain, int cellNr,
                float startSeconds):
        self.programChain = programChain
        self.cellNr = cellNr
        self.startSeconds = startSeconds

        if cellNr < 1 or \
           cellNr > self.programChain.chain.nr_of_cells:
            raise IndexError, "cell number out of range"
            
        self.cell = self.programChain.chain.cell_playback + (cellNr - 1);
        self.cellPos = self.programChain.chain.cell_position + (cellNr - 1);

    property blockMode:
        def __get__(self):
            return self.cell.block_mode

    property blockType:
        def __get__(self):
            return self.cell.block_type

    property seamlessPlay:
        def __get__(self):
            return self.cell.seamless_play != 0

    property interleaved:
        def __get__(self):
            return self.cell.interleaved != 0

    property discontinuity:
        def __get__(self):
            return self.cell.stc_discontinuity != 0

    property seamlessAngle:
        def __get__(self):
            return self.cell.seamless_angle != 0

    property playbackTime:
        def __get__(self):
            return wrapTime(&(self.cell.playback_time))

    property stillTime:
        def __get__(self):
            return self.cell.still_time

    property commandNr:
        def __get__(self):
            return self.cell.cell_cmd_nr

    property firstSector:
        def __get__(self):
            return self.cell.first_sector

    property lastVobuStartSector:
        def __get__(self):
            return self.cell.last_vobu_start_sector

    property lastSector:
        def __get__(self):
            return self.cell.last_sector

    property vobId:
        def __get__(self):
            return self.cellPos.vob_id_nr

    property cellId:
        def __get__(self):
            return self.cellPos.cell_nr

    property programNr:
        def __get__(self):
            cdef int i

            i = 2
            while i <= self.programChain.chain.nr_of_programs and \
                  self.programChain.chain.program_map[i - 1] <= self.cellNr:
                i = i + 1

            return i - 1

    def containsSector(self, int sector):
        return self.cell.first_sector <= sector <= self.cell.last_sector


cdef class ProgramChain:
    cdef readonly object container
    				# Container object
    cdef readonly int programChainNr
                                # Number in container.

    cdef pgci_srp_t *pointer	# Pointer structure to the current chain
                        	# (may be NULL).
    cdef pgc_t *chain		# Actual chain structure
    cdef vts_tmap_t *timeMap	# Time map for the chain (may be NULL).

    cdef object cells		# Array of cells

    cdef object clutArray	# A 16-position array with the color
                                # lookup table.

    def __new__(self):
        self.pointer = NULL
        self.chain = NULL

    cdef void init(self, object container, int programChainNr,
                   pgci_srp_t *chainPointer,
                   pgc_t *chain, vts_tmap_t *timeMap):
        cdef int i
        cdef float startSeconds

        self.container = container
        self.programChainNr = programChainNr

        self.pointer = chainPointer
        self.chain = chain
        self.timeMap = timeMap

        self.cells = []
        startSeconds = 0.0
        for i from 1 <= i <= self.chain.nr_of_cells:
            cell = Cell(self, i, startSeconds)
            self.cells.append(cell)
            # All cells in an interleaved block have the same start
            # time.
            if cell.blockMode != CELL_BLOCK_MODE_ANGLE_FIRST and \
               cell.blockMode != CELL_BLOCK_MODE_ANGLE_MIDDLE:
                startSeconds = startSeconds + cell.playbackTime.seconds

        self.clutArray = None

    def __richcmp__(ProgramChain self, ProgramChain other, op):
        res = (self.chain == other.chain)
        if op == 2:
            return res
        elif op == 3:
            return not res
        else:
            raise NotImplementedError

    property playbackTime:
        def __get__(self):
            return wrapTime(&(self.chain.playback_time))

    property menuType:
        def __get__(self):
            if not isinstance(self.container, VideoManager) and \
               not isinstance(self.container, LangUnit):
                return None

            if self.pointer == NULL:
                return None

            return self.pointer.entry_id & 0x0f

    property cellCount:
        # Number of cells in chain.
        def __get__(self):
            return self.chain.nr_of_cells

    def getCell(self, int cellNr):
        if cellNr < 1 or \
           cellNr > self.chain.nr_of_cells:
            raise IndexError, "cell number out of range"

        return self.cells[cellNr - 1]

    property programCount:
        # Number of programs in chain.
        def __get__(self):
            return self.chain.nr_of_programs

    def getProgramCell(self, int programNr):
        if programNr < 1 or \
           programNr > self.chain.nr_of_programs:
            raise IndexError, "program number out of range"

        return self.getCell(self.chain.program_map[programNr - 1])

    property prevProgramChain:
        def __get__(self):
            if self.chain.prev_pgc_nr == 0:
                return None
            
            return self.container.getProgramChain(self.chain.prev_pgc_nr)

    property nextProgramChain:
        def __get__(self):
            if self.chain.next_pgc_nr == 0:
                return None
            
            return self.container.getProgramChain(self.chain.next_pgc_nr)

    property goUpProgramChain:
        def __get__(self):
            if self.chain.goup_pgc_nr == 0:
                return None
            
            return self.container.getProgramChain(self.chain.goup_pgc_nr)

    def getCellFromSector(self, int sector):
        cdef int i

        for i from 0 <= i < self.chain.nr_of_cells:
            cell = self.getCell(i + 1)
            if cell.containsSector(sector):
                return cell

        return None

    property hasTimeMap:
        def __get__(self):
            return self.timeMap != NULL and self.timeMap.nr_of_entries > 0

    def getSectorFromTime(self, float seconds):
        cdef int pos

        if not self.hasTimeMap:
            raise DVDReadError, \
                  "attemp to use time map in program chain without one"

        if seconds < 0:
            seconds = 0

        pos = int(seconds + float(self.timeMap.tmu) / 2) / self.timeMap.tmu
        if pos >= self.timeMap.nr_of_entries:
            pos = self.timeMap.nr_of_entries - 1

        if pos == 0:
            return self.cells[0].firstSector
        else:
            return self.timeMap.map_ent[pos - 1] & 0x7fffffff

    def getAudioPhysStream(self, int streamNr):
        cdef uint16_t audio_control

        if not 1 <= streamNr <= 8:
            raise IndexError, "audio stream number our of range"

        audio_control = self.chain.audio_control[streamNr - 1]

        # FIXME: This may have endianness issues.
        if (audio_control >> 8) & 0x80:
            return (audio_control >> 8) & 0x7
        else:
            return None

    def getSubpicturePhysStreams(self, int streamNr):
        cdef uint32_t subp_control

        if not 1 <= streamNr <= 32:
            raise IndexError, "subpicture stream number our of range"

        subp_control = self.chain.subp_control[streamNr - 1]

        # FIXME: This may have endianness issues.
        if (subp_control >> 24) & 0x80:
            # This is to be indexed with the SUBPICTURE_PHYS_TYPE
            # constants.
            return ((subp_control >> 24) & 0x1f,
                    (subp_control >> 16) & 0x1f,
                    (subp_control >> 8) & 0x1f,
                    subp_control & 0x1f)
        else:
            return None

    property clut:
        def __get__(self):
            if self.clutArray == None:
                self.clutArray = []
                for i in range(16):
                    # FIXME: This may have endianness issues.
                    self.clutArray.append(self.chain.palette[i])

            return self.clutArray

    property preCommands:
        def __get__(self):
            if self.chain.command_tbl != NULL:
                return wrapCommandSet(self.chain.command_tbl.pre_cmds,
                                      self.chain.command_tbl.nr_of_pre)
            else:
                return wrapCommandSet(NULL, 0)

    property postCommands:
        def __get__(self):
            if self.chain.command_tbl != NULL:
                return wrapCommandSet(self.chain.command_tbl.post_cmds,
                                      self.chain.command_tbl.nr_of_post)
            else:
                return wrapCommandSet(NULL, 0)

    property cellCommands:
        def __get__(self):
            if self.chain.command_tbl != NULL:
                return wrapCommandSet(self.chain.command_tbl.cell_cmds,
                                      self.chain.command_tbl.nr_of_cell)
            else:
                return wrapCommandSet(NULL, 0)


cdef ProgramChain wrapProgramChain(object container, int programChainNr,
                                   pgci_srp_t *chainPointer, pgc_t *chain,
                                   vts_tmap_t *time_map):
    cdef ProgramChain wrapper

    wrapper = ProgramChain()
    if chain == NULL:
        wrapper.init(container, programChainNr, chainPointer,
                     chainPointer.pgc, time_map)
    else:
        wrapper.init(container, programChainNr, chainPointer, chain, time_map)
    return wrapper


cdef class LangUnit:
    cdef readonly container
    
    cdef pgci_lu_t *unit

    def __new__(self):
        self.unit = NULL

    property langCode:
        def __get__(self):
            return langCodeToString(self.unit.lang_code)

    property langExtension:
        def __get__(self):
            return self.unit.lang_extension

    property existsFlags:
        def __get__(self):
            return self.unit.exists

    property programChainCount:
        def __get__(self):
            return self.unit.pgcit.nr_of_pgci_srp

    def getProgramChain(self, int programChainNr):
        if programChainNr < 1 or \
           programChainNr > self.unit.pgcit.nr_of_pgci_srp:
            raise IndexError, "program chain number out of range"

        return wrapProgramChain(self, programChainNr, self.unit.pgcit. \
                                pgci_srp + (programChainNr - 1), NULL, NULL)

    def getMenuProgramChain(self, int menuType):
        cdef int i
        cdef pgci_srp_t *pointer

        for i from 0 <= i < self.unit.pgcit.nr_of_pgci_srp:
            pointer = self.unit.pgcit.pgci_srp + i
            if pointer.entry_id & 0x0f == menuType:
                return self.getProgramChain(i + 1)

        return None


cdef LangUnit wrapLangUnit(object container, pgci_lu_t *unit):
    cdef LangUnit wrapper

    wrapper = LangUnit()
    wrapper.container = container
    wrapper.unit = unit

    return wrapper


cdef class Chapter:
    cdef readonly VideoTitle title
    cdef readonly int chapterNr

    cdef ptt_info_t *chapter

    def __new__(self, VideoTitle title, int chapterNr):
        self.title = title
        self.chapterNr = chapterNr

        if chapterNr < 1 or \
           chapterNr > title.title.nr_of_ptts:
            raise IndexError, "chapter number out of range"

        self.chapter = title.title.ptt + (chapterNr - 1)

    property programChain:
        def __get__(self):
            return self.title.videoTitleSet. \
                   getProgramChain(self.chapter.pgcn)

    property cell:
        def __get__(self):
            return self.programChain.getProgramCell(self.chapter.pgn)

    property programNr:
        def __get__(self):
            return self.chapter.pgn


cdef class VideoTitle:
    cdef readonly VideoManager videoManager
    cdef readonly VideoTitleSet videoTitleSet
    cdef title_info_t *titleInfo
    cdef ttu_t *title

    cdef readonly int titleNrInManager

    def __new__(self, VideoManager videoManager, int titleNrInManager):
        self.videoManager = videoManager
        self.titleNrInManager = titleNrInManager

        if titleNrInManager < 1 or \
           titleNrInManager > videoManager.handle.tt_srpt.nr_of_srpts:
            raise IndexError, "video title number out of range"

        self.titleInfo = videoManager.handle.tt_srpt.title + \
                         (titleNrInManager - 1)
        self.videoTitleSet = videoManager. \
                             getVideoTitleSet(self.titleInfo.title_set_nr)
        self.title = self.videoTitleSet.handle.vts_ptt_srpt.title + \
                     (self.titleInfo.vts_ttn - 1)

    property titleNrInSet:
        def __get__(self):
            return self.titleInfo.vts_ttn

    property chapterCount:
        def __get__(self):
            return self.title.nr_of_ptts

    def getChapter(self, int chapterNr):
        return Chapter(self, chapterNr)

    property angleCount:
        def __get__(self):
            return self.titleInfo.nr_of_angles


cdef class VideoAttributes:
    cdef video_attr_t *attribs

    def __new__(self):
        self.attribs = NULL

    cdef void init(self, video_attr_t *attribs):
        self.attribs = attribs

    property allowLetterbox:
        def __get__(self):
            return self.attribs.permitted_df & 0x1 == 0

    property allowPanScan:
        def __get__(self):
            return self.attribs.permitted_df & 0x2 == 0

    property aspectRatio:
        def __get__(self):
            # Compare to an ASPECT_RATIO constant.
            return self.attribs.display_aspect_ratio

    property videoStandard:
        def __get__(self):
            # Compare to a VIDEO_STD constant
            return self.attribs.video_format

    property mpegVersion:
        def __get__(self):
            # 1 or 2
            return self.attribs.mpeg_version + 1

    property palFilmMode:
        def __get__(self):
            # Compare to a PAL_FILM_MODE constant
            return self.attribs.film_mode

    property letterboxed:
        def __get__(self):
            return self.attribs.letterboxed != 0

    property resolution:
        def __get__(self):
            if self.attribs.video_format == 0:
                return ((720, 480), (704, 480),
                        (352, 480), (352, 240))[self.attribs.picture_size]
            else:
                return ((720, 576), (704, 576),
                        (352, 576), (352, 288))[self.attribs.picture_size]

    property compressionType:
        def __get__(self):
            # Compare to a COMPRESSION_TYPE constant
            return self.attribs.bit_rate

cdef wrapVideoAttributes(video_attr_t *attribs):
    cdef VideoAttributes attributes

    attributes = VideoAttributes()
    attributes.init(attribs)

    return attributes


cdef class AudioAttributes:
    cdef audio_attr_t *attribs

    cdef readonly int streamNr

    def __new__(self):
        self.attribs = NULL

    cdef void init(self, audio_attr_t *attribs, int streamNr):
        self.attribs = attribs
        self.streamNr = streamNr

    property applicationMode:
        def __get__(self):
            return self.attribs.application_mode

    property audioFormat:
        def __get__(self):
            return self.attribs.audio_format

    property quantDRC:
        def __get__(self):
            return self.attribs.quantization

    property sampleRate:
        def __get__(self):
            return self.attribs.sample_frequency

    property channelCount:
        def __get__(self):
            return self.attribs.channels

    property langCode:
        def __get__(self):
            if self.attribs.lang_type == 1:
                return langCodeToString(self.attribs.lang_code)
            else:
                return None

    property langExtension:
        def __get__(self):
            return self.attribs.lang_extension

    property codeExtension:
        def __get__(self):
            return self.attribs.code_extension

cdef wrapAudioAttributes(audio_attr_t *attribs, int streamNr):
    cdef AudioAttributes attributes

    attributes = AudioAttributes()
    attributes.init(attribs, streamNr)

    return attributes


cdef class SubpictureAttributes:
    cdef subp_attr_t *attribs

    cdef readonly int streamNr

    def __new__(self):
        self.attribs = NULL

    cdef void init(self, subp_attr_t *attribs, int streamNr):
        self.attribs = attribs
        self.streamNr = streamNr

    property langCode:
        def __get__(self):
            if self.attribs.type == 1:
                return langCodeToString(self.attribs.lang_code)
            else:
                return None

    property subpictureFormat:
        def __get__(self):
            return self.attribs.code_mode

    property langExtension:
        def __get__(self):
            return self.attribs.lang_extension

    property codeExtension:
        def __get__(self):
            return self.attribs.code_extension

cdef wrapSubpictureAttributes(subp_attr_t *attribs, int streamNr):
    cdef SubpictureAttributes attributes

    attributes = SubpictureAttributes()
    attributes.init(attribs, streamNr)

    return attributes


cdef class VideoTitleSet:
    cdef DVDInfo dvd
    cdef ifo_handle_t *handle

    cdef readonly int titleSetNr

    def __new__(self, DVDInfo dvd, int titleSetNr):
        self.dvd = dvd
        self.titleSetNr = titleSetNr

        self.handle = ifoOpen(dvd.reader, titleSetNr)
        retries = 0
        while self.handle == NULL and retries < 3:
            time.sleep(2)
            self.handle = ifoOpen(dvd.reader, titleSetNr)
            retries = retries + 1

        if self.handle == NULL:
            raise DVDReadError, \
                  "Could not open video title set %d" % titleSetNr

    def __dealloc__(self):
        ifoClose(self.handle)

    property videoManager:
        def __get__(self):
            return self.dvd.videoManager

    property videoTitleCount:
        # Number of titles in title set.
        def __get__(self):
            return self.handle.vts_ptt_srpt.nr_of_srpts

    def getVideoTitle(self, int titleNr):
        cdef VideoManager videoManager
        cdef title_info_t *titleInfo
        cdef int i, titleNrInManager

        videoManager = self.dvd.videoManager

        # Find the title number in the video manager.
        titleNrInManager = 0
        for i from 0 <= i < videoManager.handle.tt_srpt.nr_of_srpts:
            titleInfo = videoManager.handle.tt_srpt.title + i
            if titleInfo.title_set_nr == self.titleSetNr and \
               titleInfo.vts_ttn == titleNr:
                titleNrInManager = i + 1
                break

        if titleNrInManager == 0:
            return None
        else:
            return videoManager.getVideoTitle(titleNrInManager)

    property programChainCount:
        def __get__(self):
            return self.handle.vts_pgcit.nr_of_pgci_srp

    def getProgramChain(self, int programChainNr):
        if programChainNr < 1 or \
           programChainNr > self.handle.vts_pgcit.nr_of_pgci_srp:
            raise IndexError, "program chain number out of range"

        cdef vts_tmapt_t *timeMapTable
        cdef vts_tmap_t *timeMap
        timeMapTable = self.handle.vts_tmapt
        if timeMapTable != NULL:
            timeMap = self.handle.vts_tmapt.tmap + (programChainNr - 1)
        else:
            timeMap = NULL
        return wrapProgramChain(self, programChainNr,
                                self.handle.vts_pgcit.pgci_srp + \
                                (programChainNr - 1), NULL, timeMap)

    property langUnitCount:
        def __get__(self):
            if self.handle.pgci_ut == NULL:
                return 0

            return self.handle.pgci_ut.nr_of_lus

    def getLangUnit(self, langUnitId):
        cdef int i
        cdef pgci_lu_t *unit
        cdef int langUnitNr
        cdef int code

        if isinstance(langUnitId, int):
            langUnitNr = langUnitId

            # Search for the unit by number.
            if langUnitNr < 1 or \
               langUnitNr > self.langUnitCount:
                return IndexError, "language unit number out of range"

            return wrapLangUnit(self, self.handle.pgci_ut.lu + \
                                (langUnitNr - 1))

        elif isinstance(langUnitId, str):
            # Search for the unit by language code.
            if len(langUnitId) != 2:
                return None

            code = (ord(langUnitId[0]) << 8) + ord(langUnitId[1])

            for i from 0 <= i < self.langUnitCount:
                unit = self.handle.pgci_ut.lu + i
                if unit.lang_code == code:
                    return wrapLangUnit(self, self.handle.pgci_ut.lu + i)

            return None

        else:
            raise TypeError, \
                  "getLangUnit() arg 2 must be an integer or a string"

    property menuVideoAttributes:
        def __get__(self):
            return wrapVideoAttributes(&(self.handle.vtsi_mat. \
                                         vtsm_video_attr))

    property menuAudioAttributes:
        def __get__(self):
            if self.handle.vtsi_mat.nr_of_vtsm_audio_streams == 0:
                return None

            return wrapAudioAttributes(&(self.handle.vtsi_mat. \
                                         vtsm_audio_attr), 1)

    property menuSubpictureAttributes:
        def __get__(self):
            if self.handle.vtsi_mat.nr_of_vtsm_subp_streams == 0:
                return None

            return wrapSubpictureAttributes(&(self.handle.vtsi_mat. \
                                              vtsm_subp_attr), 1)

    property videoAttributes:
        def __get__(self):
            return wrapVideoAttributes(&(self.handle.vtsi_mat. \
                                         vts_video_attr))

    property audioStreamCount:
        def __get__(self):
            return self.handle.vtsi_mat.nr_of_vts_audio_streams

    def getAudioAttributes(self, int streamNr):
        if streamNr < 1 or \
           streamNr > self.handle.vtsi_mat.nr_of_vts_audio_streams:
            raise IndexError, "audio stream number out of range"

        return wrapAudioAttributes(&(self.handle.vtsi_mat. \
                                     vts_audio_attr[streamNr - 1]),
                                   streamNr)

    property subpictureStreamCount:
        def __get__(self):
            return self.handle.vtsi_mat.nr_of_vts_subp_streams

    def getSubpictureAttributes(self, int streamNr):
        if streamNr < 1 or \
           streamNr > self.handle.vtsi_mat.nr_of_vts_subp_streams:
            raise IndexError, "subpicture stream number out of range"

        return wrapSubpictureAttributes(&(self.handle.vtsi_mat. \
                                          vts_subp_attr[streamNr - 1]),
                                        streamNr)


cdef class VideoManager:
    cdef readonly DVDInfo dvd
    cdef ifo_handle_t *handle

    cdef videoTitleSets

    def __new__(self, DVDInfo dvd):
        cdef int i

        self.dvd = dvd
        self.handle = ifoOpen(dvd.reader, 0)

        self.videoTitleSets = []
        for i from 1 <= i <= self.handle.vmgi_mat.vmg_nr_of_title_sets:
            self.videoTitleSets.append(VideoTitleSet(self.dvd, i))

    def __dealloc__(self):
        ifoClose(self.handle)

    property titleSetNr:
        def __get__(self):
            # By convention, the video manager corresponds to title set 0.
            return 0

    property volumeCount:
        def __get__(self):
            return self.handle.vmgi_mat.vmg_nr_of_volumes

    property volumeNumber:
        def __get__(self):
            return self.handle.vmgi_mat.vmg_this_volume_nr

    property discSide:
        def __get__(self):
            return self.handle.vmgi_mat.disc_side

    property providerID:
        def __get__(self):
            return self.handle.vmgi_mat.provider_identifier

    property firstPlay:
        def __get__(self):
            return wrapProgramChain(self, 0, NULL, self.handle.first_play_pgc,
                                    NULL)

    property videoTitleSetCount:
        def __get__(self):
            return self.handle.vmgi_mat.vmg_nr_of_title_sets

    def getVideoTitleSet(self, int titleSetNr):
        if titleSetNr < 1 or \
           titleSetNr > self.handle.vmgi_mat.vmg_nr_of_title_sets:
            raise IndexError, "video title set number out of range"

        return self.videoTitleSets[titleSetNr - 1]

    property videoTitleCount:
        def __get__(self):
            return self.handle.tt_srpt.nr_of_srpts

    def getVideoTitle(self, int titleNr):
        return VideoTitle(self, titleNr)

    property langUnitCount:
        def __get__(self):
            if self.handle.pgci_ut == NULL:
                return 0

            return self.handle.pgci_ut.nr_of_lus

    def getLangUnit(self, langUnitId):
        cdef int i
        cdef pgci_lu_t *unit
        cdef int langUnitNr
        cdef int code

        if isinstance(langUnitId, int):
            langUnitNr = langUnitId

            # Search for the unit by number.
            if langUnitNr < 1 or \
               langUnitNr > self.langUnitCount:
                return IndexError, "language unit number out of range"

            return wrapLangUnit(self, self.handle.pgci_ut.lu + \
                                (langUnitNr - 1))

        elif isinstance(langUnitId, str):
            # Search for the unit by language code.
            if len(langUnitId) != 2:
                return None

            code = (ord(langUnitId[0]) << 8) + ord(langUnitId[1])

            for i from 0 <= i < self.langUnitCount:
                unit = self.handle.pgci_ut.lu + i
                if unit.lang_code == code:
                    return wrapLangUnit(self, self.handle.pgci_ut.lu + i)

            return None

        else:
            raise TypeError, \
                  "getLangUnit() arg 2 must be an integer or a string"

    property menuVideoAttributes:
        def __get__(self):
            return wrapVideoAttributes(&(self.handle.vmgi_mat. \
                                         vmgm_video_attr))

    property menuAudioAttributes:
        def __get__(self):
            if self.handle.vmgi_mat.nr_of_vmgm_audio_streams == 0:
                return None

            return wrapAudioAttributes(&(self.handle.vmgi_mat. \
                                         vmgm_audio_attr), 1)

    property menuSubpictureAttributes:
        def __get__(self):
            if self.handle.vmgi_mat.nr_of_vmgm_subp_streams == 0:
                return None

            return wrapSubpictureAttributes(&(self.handle.vmgi_mat. \
                                              vmgm_subp_attr), 1)


cdef class DVDInfo:
    cdef dvd_reader_t *reader

    cdef vmg

    def __new__(self, path):
        self.reader = DVDOpen(path)
        if self.reader == NULL:
            raise IOError, 'Cannot open DVD in path %s' % path

        self.vmg = VideoManager(self)

        DVDClose(self.reader)

    def ifoPrint(self, int title):
        ifoPrint(self.reader, title)

    property videoManager:
        def __get__(self):
            return self.vmg


#
# NAV Packet Support
#

include "nav_types.pyx"

cdef extern from "dvdread/nav_read.h":
    void navRead_PCI(pci_t *pci, unsigned char *buffer)
    void navRead_DSI(dsi_t *dsi, unsigned char *buffer)

cdef class NavPacket


cdef class Button:
    cdef readonly NavPacket nav
    cdef btni_t *btn

    property area:
        def __get__(self):
            return (self.btn.x_start, self.btn.y_start,
                    self.btn.x_end, self.btn.y_end)

    property up:
        def __get__(self):
            return self.btn.up

    property down:
        def __get__(self):
            return self.btn.down

    property left:
        def __get__(self):
            return self.btn.left

    property right:
        def __get__(self):
            return self.btn.right

    property autoAction:
        def __get__(self):
            return self.btn.auto_action_mode != 0

    property paletteSelected:
        def __get__(self):
            return self.nav.pci.hli.btn_colit. \
                   btn_coli[self.btn.btn_coln - 1][0]

    property paletteAction:
        def __get__(self):
            return self.nav.pci.hli.btn_colit. \
                   btn_coli[self.btn.btn_coln - 1][1]

    property command:
        def __get__(self):
            return wrapCommand(&(self.btn.cmd))

cdef wrapButton(NavPacket nav, btni_t *btn):
    cdef Button button

    button = Button()
    button.nav = nav
    button.btn = btn

    return button


cdef getSimplePointer(unsigned long value):
    if value & 0x3fffffff == 0x3fffffff:
        return None

    return value & 0x3fffffff

cdef getBidiPointer(unsigned long value):
    if value == 0x7fffffff:
        return None

    ptr = long(value & 0x7fffffff)
    if value & 0x10000000:
        return -ptr
    else:
        return ptr

cdef class NavPacket:
    cdef pci_t pci
    cdef dsi_t dsi

    def __new__(self, buffer):
        cdef char *data
        cdef int length

        if PyObject_AsReadBuffer(buffer, &data, &length):
            raise TypeError, 'buffer parameter not a buffer object'

        if length < 2048:
            raise ValueError, 'buffer size should be 2048 or more'

        navRead_PCI(&self.pci, <unsigned char *>data + 0x2d);
        navRead_DSI(&self.dsi, <unsigned char *>data + 0x407);


    #
    # Navigation
    #

    property nextVobu:
        def __get__(self):
            return getSimplePointer(self.dsi.vobu_sri.next_vobu)

    property prevVobu:
        def __get__(self):
            return getSimplePointer(self.dsi.vobu_sri.prev_vobu)

    def getForwardVobu(self, int intervalId):
        cdef uint32_t offset

        if intervalId < 0 or intervalId > 18:
            raise IndexError, "forward VOBU interval id out of range"

        offset = self.dsi.vobu_sri.fwda[intervalId]
        if offset & 0x80000000:
            return offset & 0x3fffffff
        else:
            return None

    def getBackwardVobu(self, int intervalId):
        cdef uint32_t offset

        if intervalId < 0 or intervalId > 18:
            raise IndexError, "backward VOBU interval id out of range"

        offset = self.dsi.vobu_sri.bwda[intervalId]
        if offset & 0x80000000:
            return offset & 0x3fffffff
        else:
            return None

    property nextVideoVobu:
        def __get__(self):
            return getSimplePointer(self.dsi.vobu_sri.next_video)

    property prevVideoVobu:
        def __get__(self):
            return getSimplePointer(self.dsi.vobu_sri.prev_video)


    #
    # Time
    #

    property startTime:
        def __get__(self):
            return self.pci.pci_gi.vobu_s_ptm

    property endTime:
        def __get__(self):
            return self.pci.pci_gi.vobu_e_ptm

    property cellElapsedTime:
        def __get__(self):
            return wrapTime(&(self.pci.pci_gi.e_eltm))


    #
    # Buttons
    #

    property buttonCount:
        def __get__(self):
            return self.pci.hli.hl_gi.btn_ns

    def getButton(self, int buttonNr, int subpictureType):
        cdef int groupCount
        cdef int mask
        cdef int group
        cdef int buttonPos

        if not 1 <= buttonNr <= self.pci.hli.hl_gi.btn_ns:
            raise IndexError, "button number out of range"

        # Calculate the mask.
        if subpictureType == SUBPICTURE_PHYS_TYPE_4_3:
            mask = 0
        elif subpictureType == SUBPICTURE_PHYS_TYPE_WIDESCREEN:
            mask = 1
        elif subpictureType == SUBPICTURE_PHYS_TYPE_LETTERBOX:
            mask = 2
        elif subpictureType == SUBPICTURE_PHYS_TYPE_PAN_SCAN:
            mask = 4
        else:
            raise IndexError, "subpicture type out of range"

        groupCount = self.pci.hli.hl_gi.btngr_ns
        if not 1 <= groupCount <= 3:
            # This shouln't happen, but you never know.
            groupCount = 1

        if mask != 0:
            group = -1

            # Try finding a group that matches the mask exactly.
            if groupCount >= 1 and \
               self.pci.hli.hl_gi.btngr1_dsp_ty & mask:
                group = 0
            elif groupCount >= 2 and \
                 self.pci.hli.hl_gi.btngr2_dsp_ty & mask:
                group = 1
            elif groupCount >= 3 and \
                 self.pci.hli.hl_gi.btngr3_dsp_ty & mask:
                group = 3

        if mask == 0 or group == -1:
            # Look for a standard 4:3 group.
            if groupCount >= 1 and \
               self.pci.hli.hl_gi.btngr1_dsp_ty == 0:
                group = 0
            elif groupCount >= 2 and \
                 self.pci.hli.hl_gi.btngr2_dsp_ty == 0:
                group = 1
            elif groupCount >= 3 and \
                 self.pci.hli.hl_gi.btngr3_dsp_ty == 0:
                group = 3

        if group == -1:
            # We have a funny situation here. Just pick an arbitrary
            # group and hope for the best.
            group = 0

        buttonPos = (36 / groupCount) * group + buttonNr - 1
        return wrapButton(self, &(self.pci.hli.btnit[buttonPos]))

    property highlightStatus:
        def __get__(self):
            return self.pci.hli.hl_gi.hli_ss

    property forcedSelect:
        def __get__(self):
            return self.pci.hli.hl_gi.fosl_btnn

    property forcedActivate:
        def __get__(self):
            return self.pci.hli.hl_gi.foac_btnn

    #
    # Angles
    #

    def getNonSeamlessNextVobu(self, angleNr):
        if not 1 <= angleNr <= 9:
            raise IndexError, "Angle number out of range"

        return getBidiPointer(self.pci. \
                              nsml_agli.nsml_agl_dsta[angleNr - 1])

    property preInterleaved:
        def __get__(self):
            return self.dsi.sml_pbi.category & 0x8000;

    property interleaved:
        def __get__(self):
            return self.dsi.sml_pbi.category & 0x4000;

    property unitStart:
        def __get__(self):
            return self.dsi.sml_pbi.category & 0x2000;

    property unitEnd:
        def __get__(self):
            return self.dsi.sml_pbi.category & 0x1000;

    property seamlessEndInterleavedUnit:
        def __get__(self):
            return self.dsi.sml_pbi.ilvu_ea

    property seamlessNextInterleavedUnit:
        def __get__(self):
            return self.dsi.sml_pbi.ilvu_sa

    property seamlessInterlevedUnitSize:
        def __get__(self):
            return self.dsi.sml_pbi.size

    def getSeamlessNextInterleavedUnit(self, angleNr):
        if not 1 <= angleNr <= 9:
            raise IndexError, "Angle number out of range"

        return getBidiPointer(self.dsi. \
                              sml_agli.data[angleNr - 1].address)

    def getSeamlessNextInterleavedUnitSize(self, angleNr):
        if not 1 <= angleNr <= 9:
            raise IndexError, "Angle number out of range"

        return self.dsi.sml_agli.data[angleNr - 1].size


    #
    # Audio and Subpicture Streams
    #

    def getFirstAudioOffset(self, int streamNr):
        if streamNr < 1 or streamNr > 8:
            raise IndexError, "audio stream number out of range"

        return self.dsi.synci.a_synca[streamNr - 1]

    def getFirstSubpictureOffset(self, int streamNr):
        if streamNr < 1 or streamNr > 32:
            raise IndexError, "subpicture stream number out of range"

        return self.dsi.synci.sp_synca[streamNr - 1]
