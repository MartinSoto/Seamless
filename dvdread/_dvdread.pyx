# -*- Python -*-

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


# Supported aspect ratios.
ASPECT_RATIO_4_3 = 0
ASPECT_RATIO_NOT_SPECIFIED = 1
ASPECT_RATIO_RESERVED = 2
ASPECT_RATIO_16_9 = 3


# Possible video modes.
VIDEO_MODE_NORMAL = 0
VIDEO_MODE_PAN_SCAN = 1
VIDEO_MODE_LETTERBOX = 2
VIDEO_MODE_RESERVED = 3


# Possible highlight statuses.
HLSTATUS_NONE = 0		# No highlight info.
HLSTATUS_NEW_INFO = 1		# New highlight info.
HLSTATUS_PREVIOUS = 2		# Equal to previous nav packet.
HLSTATUS_PREVIOUS_CMDS = 3	# Equal to previous nav except for commands.


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
                                # begining of the program chain.

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

    property lastVOBUStartSector:
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
    cdef vts_tmap_t *time_map	# Time map for the chain (may be NULL).

    cdef object cells		# Array of cells

    def __new__(self):
        self.pointer = NULL
        self.chain = NULL

    cdef void init(self, object container, int programChainNr,
                   pgci_srp_t *chainPointer,
                   pgc_t *chain, vts_tmap_t *time_map):
        cdef int i
        cdef float startSeconds

        self.container = container
        self.programChainNr = programChainNr

        self.pointer = chainPointer
        self.chain = chain
        self.time_map = time_map

        self.cells = []
        startSeconds = 0.0
        for i from 1 <= i <= self.chain.nr_of_cells:
            cell = Cell(self, i, startSeconds)
            self.cells.append(cell)
            startSeconds = startSeconds + cell.playbackTime.seconds

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
            return self.time_map != NULL and self.time_map.nr_of_entries > 0

    def getSectorFromTime(self, float seconds):
        cdef int pos

        if not self.hasTimeMap:
            raise DVDReadError, \
                  "attemp to use time map in program chain without one"

        if seconds < 0:
            seconds = 0

        pos = int(seconds + float(self.time_map.tmu) / 2) / self.time_map.tmu
        if pos >= self.time_map.nr_of_entries:
            pos = self.time_map.nr_of_entries - 1

        if pos == 0:
            return self.cells[0].firstSector
        else:
            return self.time_map.map_ent[pos - 1] & 0x7fffffff

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
            return {'4:3': (subp_control >> 24) & 0x1f,
                    'widescreen': (subp_control >> 16) & 0x1f,
                    'letterbox': (subp_control >> 8) & 0x1f,
                    'pan&scan': subp_control & 0x1f}
        else:
            return None

    def getCLUTEntry(self, int entryNr):
        if not 1 <= entryNr <= 16:
            raise IndexError, "CLUT entry number out of range"

        # FIXME: This may have endianness issues.
        return self.chain.palette[entryNr - 1]

    property preCommands:
        def __get__(self):
            return wrapCommandSet(self.chain.command_tbl.pre_cmds,
                                  self.chain.command_tbl.nr_of_pre)

    property postCommands:
        def __get__(self):
            return wrapCommandSet(self.chain.command_tbl.post_cmds,
                                  self.chain.command_tbl.nr_of_post)

    property cellCommands:
        def __get__(self):
            return wrapCommandSet(self.chain.command_tbl.cell_cmds,
                                  self.chain.command_tbl.nr_of_cell)


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
    cdef readonly VideoTitleSet videoTitleSet
    cdef ttu_t *title

    cdef readonly int titleNr

    def __new__(self, VideoTitleSet videoTitleSet, int titleNr):
        self.videoTitleSet = videoTitleSet
        self.titleNr = titleNr

        if titleNr < 1 or \
           titleNr > videoTitleSet.handle.vts_ptt_srpt.nr_of_srpts:
            raise IndexError, "video title number out of range"

        self.title = videoTitleSet.handle.vts_ptt_srpt.title + (titleNr - 1)

    property globalTitleNr:
        def __get__(self):
            return self.videoTitleSet.videoManager.findVideoTitle(self)

    property chapterCount:
        def __get__(self):
            return self.title.nr_of_ptts

    def getChapter(self, int chapterNr):
        return Chapter(self, chapterNr)


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
        return VideoTitle(self, titleNr)

    property programChainCount:
        def __get__(self):
            return self.handle.vts_pgcit.nr_of_pgci_srp

    def getProgramChain(self, int programChainNr):
        if programChainNr < 1 or \
           programChainNr > self.handle.vts_pgcit.nr_of_pgci_srp:
            raise IndexError, "program chain number out of range"

        return wrapProgramChain(self, programChainNr,
                                self.handle.vts_pgcit.pgci_srp + \
                                (programChainNr - 1), NULL,
                                self.handle.vts_tmapt.tmap)

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
        cdef title_info_t *titleInfo

        if titleNr < 1 or \
           titleNr > self.handle.tt_srpt.nr_of_srpts:
            raise IndexError, "video title number out of range"

        titleInfo = self.handle.tt_srpt.title + (titleNr - 1)
        return self.getVideoTitleSet(titleInfo.title_set_nr). \
               getVideoTitle(titleInfo.vts_ttn)

    def findVideoTitle(self, VideoTitle title):
        """Finds a video title in the video manager.
        
        Returns the position of this video title in the global video
        title table contained in the video manager."""

        cdef title_info_t *titleInfo
        cdef int i, vtsNr, titleNr

        vtsNr = title.videoTitleSet.titleSetNr
        titleNr = title.titleNr
        for i from 0 <= i < self.handle.tt_srpt.nr_of_srpts:
            titleInfo = self.handle.tt_srpt.title + i
            if titleInfo.title_set_nr == vtsNr and \
               titleInfo.vts_ttn == titleNr:
                return i + 1

        return None

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

    property nextVOBU:
        def __get__(self):
            return self.dsi.vobu_sri.next_vobu & 0x3fffffff

    property prevVOBU:
        def __get__(self):
            return self.dsi.vobu_sri.prev_vobu & 0x3fffffff

    def getForwardVOBU(self, int intervalId):
        cdef uint32_t offset

        if intervalId < 0 or intervalId > 18:
            raise IndexError, "forward VOBU interval id out of range"

        offset = self.dsi.vobu_sri.fwda[intervalId]
        if offset & 0x80000000:
            return offset & 0x3fffffff
        else:
            return None

    def getBackwardVOBU(self, int intervalId):
        cdef uint32_t offset

        if intervalId < 0 or intervalId > 18:
            raise IndexError, "backward VOBU interval id out of range"

        offset = self.dsi.vobu_sri.bwda[intervalId]
        if offset & 0x80000000:
            return offset & 0x3fffffff
        else:
            return None

    property nextVideoVOBU:
        def __get__(self):
            return self.dsi.vobu_sri.next_video & 0x3fffffff

    property prevVideoVOBU:
        def __get__(self):
            return self.dsi.vobu_sri.prev_video & 0x3fffffff

    property startTime:
        def __get__(self):
            return self.pci.pci_gi.vobu_s_ptm

    property endTime:
        def __get__(self):
            return self.pci.pci_gi.vobu_e_ptm

    property cellElapsedTime:
        def __get__(self):
            return wrapTime(&(self.pci.pci_gi.e_eltm))

    property buttonCount:
        def __get__(self):
            return self.pci.hli.hl_gi.btn_ns

    def getButton(self, buttonNr):
        if buttonNr < 1 or buttonNr > 36:
            raise IndexError, "button number out of range"

        return wrapButton(self, &(self.pci.hli.btnit[buttonNr - 1]))

    property highlightStatus:
        def __get__(self):
            return self.pci.hli.hl_gi.hli_ss

    property forcedSelect:
        def __get__(self):
            return self.pci.hli.hl_gi.fosl_btnn

    property forcedActivate:
        def __get__(self):
            return self.pci.hli.hl_gi.foac_btnn
