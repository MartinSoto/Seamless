# -*- Python -*-
# Seamless DVD Player
# Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
# This file copyright (C) 2000, 2001
#     Björn Englund <d4bjorn@dtek.chalmers.se>,
#     Håkan Hjort <d95hjort@dtek.chalmers.se>
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

cdef extern from "dvdread/ifo_types.h":
  # Basic integer types.
  ctypedef unsigned char uint8_t
  ctypedef unsigned short uint16_t
  ctypedef unsigned int uint32_t
  ctypedef unsigned long long uint64_t

  # Common
  # The following structures are used in both the VMGI and VTSI.

  # DVD Time Information.
  ctypedef struct dvd_time_t:
    uint8_t hour	# Hour, in binary coded decimal format.
    uint8_t minute	# Minute, in binary coded decimal format.
    uint8_t second	# Second, in binary coded decimal format.
    uint8_t frame_u 	# Additional frames, in binary coded decimal
  			# format. The two high bits are the frame rate.


  # Type to store per-command data.
  ctypedef struct vm_cmd_t:
    uint8_t bytes[8]


  # Video Attributes.
  ctypedef struct video_attr_t:
    unsigned int permitted_df	# High bit: Disallow automatic pan/scan.
    				# Low bit: Disallow automatic letterbox.
    unsigned int display_aspect_ratio
    unsigned int video_format
    unsigned int mpeg_version

    unsigned int film_mode
    unsigned int letterboxed

    unsigned int picture_size
    unsigned int bit_rate
    unsigned int line21_cc_2
    unsigned int line21_cc_1


  # Karaoke Info
  cdef struct karaoke_t:
    unsigned int mode
    unsigned int mc_intro
    unsigned int version
    unsigned int channel_assignment

  # Surround Info
  cdef struct surround_t:
    unsigned int dolby_encoded

  # Application info
  cdef union app_info_t:
    karaoke_t karaoke
    surround_t surround

  # Audio Attributes.
  ctypedef struct audio_attr_t:
    unsigned int application_mode
    unsigned int lang_type
    unsigned int multichannel_extension
    unsigned int audio_format

    unsigned int channels
    unsigned int sample_frequency
    unsigned int quantization

    uint16_t lang_code
    uint8_t lang_extension
    uint8_t code_extension
    app_info_t app_info


  # MultiChannel Extension
  ctypedef struct multichannel_ext_t:
    unsigned int ach0_gme

    unsigned int ach1_gme

    unsigned int ach2_gm2e
    unsigned int ach2_gm1e
    unsigned int ach2_gv2e
    unsigned int ach2_gv1e

    unsigned int ach3_se2e
    unsigned int ach3_gmAe
    unsigned int ach3_gv2e
    unsigned int ach3_gv1e

    unsigned int ach4_seBe
    unsigned int ach4_gmBe
    unsigned int ach4_gv2e
    unsigned int ach4_gv1e


  # Subpicture Attributes.
  ctypedef struct subp_attr_t:
    # type: 0 not specified
    #       1 language
    #       2 other
    # coding mode: 0 run length
    #              1 extended
    #              2 other
    # language: indicates language if type == 1
    # lang extension: if type == 1 contains the lang extension

    unsigned int type
    unsigned int code_mode

    uint16_t lang_code
    uint8_t lang_extension
    uint8_t code_extension


  # PGC Command Table.
  ctypedef struct pgc_command_tbl_t:
    uint16_t nr_of_pre
    uint16_t nr_of_post
    uint16_t nr_of_cell
    vm_cmd_t *pre_cmds
    vm_cmd_t *post_cmds
    vm_cmd_t *cell_cmds


  # PGC Program Map
  ctypedef uint8_t pgc_program_map_t


  # Cell Playback Information.
  ctypedef struct cell_playback_t:
    unsigned int seamless_angle
    unsigned int stc_discontinuity
    unsigned int interleaved
    unsigned int seamless_play
    unsigned int block_type
    unsigned int block_mode

    unsigned int restricted
    unsigned int playback_mode

    uint8_t still_time
    uint8_t cell_cmd_nr
    dvd_time_t playback_time
    uint32_t first_sector
    uint32_t first_ilvu_end_sector
    uint32_t last_vobu_start_sector
    uint32_t last_sector


  # Cell Position Information.
  ctypedef struct cell_position_t:
    uint16_t vob_id_nr
    uint8_t cell_nr


  # User Operations.
  ctypedef struct user_ops_t:
    unsigned int video_pres_mode_change # 24

    unsigned int resume # 16
    unsigned int button_select_or_activate
    unsigned int still_off
    unsigned int pause_on
    unsigned int audio_stream_change
    unsigned int subpic_stream_change
    unsigned int angle_change
    unsigned int karaoke_audio_pres_mode_change # 23

    unsigned int forward_scan # 8
    unsigned int backward_scan
    unsigned int title_menu_call
    unsigned int root_menu_call
    unsigned int subpic_menu_call
    unsigned int audio_menu_call
    unsigned int angle_menu_call
    unsigned int chapter_menu_call # 15

    unsigned int title_or_time_play # 0
    unsigned int chapter_search_or_play
    unsigned int title_play
    unsigned int stop
    unsigned int go_up
    unsigned int time_or_chapter_search
    unsigned int prev_or_top_pg_search
    unsigned int next_pg_search # 7


  # Program Chain Information.
  ctypedef struct pgc_t:
    uint8_t nr_of_programs
    uint8_t nr_of_cells
    dvd_time_t playback_time
    user_ops_t prohibited_ops
    uint16_t audio_control[8] # New type?
    uint32_t subp_control[32] # New type?
    uint16_t next_pgc_nr
    uint16_t prev_pgc_nr
    uint16_t goup_pgc_nr
    uint8_t still_time
    uint8_t pg_playback_mode
    uint32_t palette[16] # New type struct {zero_1, Y, Cr, Cb} ?
    uint16_t command_tbl_offset
    uint16_t program_map_offset
    uint16_t cell_playback_offset
    uint16_t cell_position_offset
    pgc_command_tbl_t *command_tbl
    pgc_program_map_t *program_map
    cell_playback_t *cell_playback
    cell_position_t *cell_position


  # Program Chain Information Search Pointer.
  ctypedef struct pgci_srp_t:
    uint8_t entry_id
    unsigned int block_type	# Like in cell playback
    unsigned int block_mode	# Like in cell playback
    uint16_t ptl_id_mask
    uint32_t pgc_start_byte
    pgc_t *pgc


  # Program Chain Information Table.
  ctypedef struct pgcit_t:
    uint16_t nr_of_pgci_srp	# Number of program chains.
    uint32_t last_byte
    pgci_srp_t *pgci_srp


  # Menu PGCI Language Unit.
  ctypedef struct pgci_lu_t:
    uint16_t lang_code		# ISO 639 language code.
    uint8_t lang_extension
    uint8_t exists		# Menu existence flags.
    uint32_t lang_start_byte
    pgcit_t *pgcit


  # Menu PGCI Unit Table.
  ctypedef struct pgci_ut_t:
    uint16_t nr_of_lus
    uint32_t last_byte
    pgci_lu_t *lu


  # Cell Address Information.
  ctypedef struct cell_adr_t:
    uint16_t vob_id
    uint8_t cell_id
    uint32_t start_sector
    uint32_t last_sector


  # Cell Address Table.
  ctypedef struct c_adt_t:
    uint16_t nr_of_vobs # VOBs
    uint32_t last_byte
    cell_adr_t *cell_adr_table # No explicit size given.


  # VOBU Address Map.
  ctypedef struct vobu_admap_t:
    uint32_t last_byte
    uint32_t *vobu_start_sectors


  # VMGI
  # The following structures relate to the Video Manager.

  # Video Manager Information Management Table.
  ctypedef struct vmgi_mat_t:
    char vmg_identifier[12]
    uint32_t vmg_last_sector
    uint32_t vmgi_last_sector
    uint8_t specification_version
    uint32_t vmg_category
    uint16_t vmg_nr_of_volumes
    uint16_t vmg_this_volume_nr
    uint8_t disc_side
    uint16_t vmg_nr_of_title_sets
    				# Number of video title sets.
    char provider_identifier[32]
    uint64_t vmg_pos_code
    uint32_t vmgi_last_byte
    uint32_t first_play_pgc
    uint32_t vmgm_vobs # sector
    uint32_t tt_srpt # sector
    uint32_t vmgm_pgci_ut # sector
    uint32_t ptl_mait # sector
    uint32_t vts_atrt # sector
    uint32_t txtdt_mgi # sector
    uint32_t vmgm_c_adt # sector
    uint32_t vmgm_vobu_admap # sector

    video_attr_t vmgm_video_attr
    uint8_t nr_of_vmgm_audio_streams # should be 0 or 1
    audio_attr_t vmgm_audio_attr
    uint8_t nr_of_vmgm_subp_streams # should be 0 or 1
    subp_attr_t vmgm_subp_attr

  ctypedef struct playback_type_t:
    unsigned int title_or_time_play
    unsigned int chapter_search_or_play
    unsigned int jlc_exists_in_tt_dom
    unsigned int jlc_exists_in_button_cmd
    unsigned int jlc_exists_in_prepost_cmd
    unsigned int jlc_exists_in_cell_cmd
    unsigned int multi_or_random_pgc_title


  # Title Information.
  ctypedef struct title_info_t:
    playback_type_t pb_ty
    uint8_t nr_of_angles	# Number of angles.
    uint16_t nr_of_ptts		# Number of chapters.
    uint16_t parental_id
    uint8_t title_set_nr	# Video title set (VTS) number.
    uint8_t vts_ttn		# Number within VTS
    uint32_t title_set_sector	# Start sector for VTS, with respect to
  				# whole disk origin.


  # PartOfTitle Search Pointer Table.
  ctypedef struct tt_srpt_t:
    uint16_t nr_of_srpts
    uint32_t last_byte
    title_info_t *title


  # Parental Management Information Unit Table.
  # Level 1 (US: G), ..., 7 (US: NC-17), 8
  ctypedef uint16_t pf_level_t[8]


  # Parental Management Information Unit Table.
  ctypedef struct ptl_mait_country_t:
    uint16_t country_code
    uint16_t pf_ptl_mai_start_byte
    pf_level_t *pf_ptl_mai # table of (nr_of_vtss + 1), video_ts is first


  # Parental Management Information Table.
  ctypedef struct ptl_mait_t:
    uint16_t nr_of_countries
    uint16_t nr_of_vtss
    uint32_t last_byte
    ptl_mait_country_t *countries


  # Video Title Set Attributes.
  ctypedef struct vts_attributes_t:
    uint32_t last_byte
    uint32_t vts_cat

    video_attr_t vtsm_vobs_attr
    uint8_t nr_of_vtsm_audio_streams # should be 0 or 1
    audio_attr_t vtsm_audio_attr
    uint8_t nr_of_vtsm_subp_streams # should be 0 or 1
    subp_attr_t vtsm_subp_attr

    video_attr_t vtstt_vobs_video_attr
    uint8_t nr_of_vtstt_audio_streams
    audio_attr_t vtstt_audio_attr[8]
    uint8_t nr_of_vtstt_subp_streams
    subp_attr_t vtstt_subp_attr[32]


  # Video Title Set Attribute Table.
  ctypedef struct vts_atrt_t:
    uint16_t nr_of_vtss
    uint32_t last_byte
    vts_attributes_t *vts
    uint32_t *vts_atrt_offsets # offsets table for each vts_attributes


  # Text Data. (Incomplete)
  ctypedef struct txtdt_t:
    uint32_t last_byte # offsets are relative here
    uint16_t offsets[100] # == nr_of_srpts + 1 (first is disc title)


  # Text Data Language Unit. (Incomplete)
  ctypedef struct txtdt_lu_t:
    uint16_t lang_code
    uint16_t unknown # 0x0001, title 1? disc 1? side 1?
    uint32_t txtdt_start_byte # prt, rel start of vmg_txtdt_mgi
    txtdt_t *txtdt


  # Text Data Manager Information. (Incomplete)
  ctypedef struct txtdt_mgi_t:
    char disc_name[14] # how many bytes??
    uint16_t nr_of_language_units # 32bit??
    uint32_t last_byte
    txtdt_lu_t *lu


  # VTS
  # Structures relating to the Video Title Set (VTS).

  # Video Title Set Information Management Table.
  ctypedef struct vtsi_mat_t:
    char vts_identifier[12]
    uint32_t vts_last_sector
    uint32_t vtsi_last_sector
    uint8_t specification_version
    uint32_t vts_category
    uint32_t vtsi_last_byte
    uint32_t vtsm_vobs # sector
    uint32_t vtstt_vobs # sector
    uint32_t vts_ptt_srpt # sector
    uint32_t vts_pgcit # sector
    uint32_t vtsm_pgci_ut # sector
    uint32_t vts_tmapt # sector
    uint32_t vtsm_c_adt # sector
    uint32_t vtsm_vobu_admap # sector
    uint32_t vts_c_adt # sector
    uint32_t vts_vobu_admap # sector

    video_attr_t vtsm_video_attr
    uint8_t nr_of_vtsm_audio_streams # should be 0 or 1
    audio_attr_t vtsm_audio_attr
    uint8_t nr_of_vtsm_subp_streams # should be 0 or 1
    subp_attr_t vtsm_subp_attr

    video_attr_t vts_video_attr
    uint8_t nr_of_vts_audio_streams
    audio_attr_t vts_audio_attr[8]
    uint8_t nr_of_vts_subp_streams
    subp_attr_t vts_subp_attr[32]
    multichannel_ext_t vts_mu_audio_attr[8]


  # PartOfTitle Unit Information.
  ctypedef struct ptt_info_t:
    uint16_t pgcn		# Program chain number.
    uint16_t pgn		# Program number.


  # PartOfTitle Information.
  ctypedef struct ttu_t:
    uint16_t nr_of_ptts		# Number of chapters.
    ptt_info_t *ptt		# Chapter array.


  # PartOfTitle Search Pointer Table.
  ctypedef struct vts_ptt_srpt_t:
    uint16_t nr_of_srpts	# Number of titles.
    uint32_t last_byte
    ttu_t *title		# Title array.
    uint32_t *ttu_offset	# offset table for each ttu


  # Time Map Entry.

  # Should this be bit field at all or just the uint32_t?
  ctypedef uint32_t map_ent_t

  # Time Map.
  ctypedef struct vts_tmap_t:
    uint8_t tmu # Time unit, in seconds
    uint16_t nr_of_entries
    map_ent_t *map_ent		# Theory: The first entry corresponds
  				# to time tmu. For time 0 the first
  				# sector of first cell must be used.


  # Time Map Table.
  ctypedef struct vts_tmapt_t:
    uint16_t nr_of_tmaps
    uint32_t last_byte
    vts_tmap_t *tmap
    uint32_t *tmap_offset # offset table for each tmap


  # The following structure defines an IFO file.  The structure is
  # divided into two parts, the VMGI, or Video Manager Information,
  # which is read from the VIDEO_TS.[IFO,BUP] file, and the VTSI, or
  # Video Title Set Information, which is read in from the
  # VTS_XX_0.[IFO,BUP] files.
  ctypedef struct ifo_handle_t:
    dvd_file_t *file

    # VMGI
    vmgi_mat_t *vmgi_mat	# Video manager information management table.
    tt_srpt_t *tt_srpt		# Table of titles.
    pgc_t *first_play_pgc	# First play program chain.
    ptl_mait_t *ptl_mait	# Parental management table.
    vts_atrt_t *vts_atrt	# Video Title Set Attribute Table.
    txtdt_mgi_t *txtdt_mgi	# Text Data Manager Information

    # Common
    pgci_ut_t *pgci_ut		# Menu program chain information unit table.
    c_adt_t *menu_c_adt		# Menu cell address table.
    vobu_admap_t *menu_vobu_admap
    				# Menu VOBU address table.

    # VTSI
    vtsi_mat_t *vtsi_mat	# VTS information manager table.
    vts_ptt_srpt_t *vts_ptt_srpt
    				# Part of title search pointer table.
    pgcit_t *vts_pgcit		# Program chain information table.
    vts_tmapt_t *vts_tmapt	# Time map table.
    c_adt_t *vts_c_adt		# Title cell address table.
    vobu_admap_t *vts_vobu_admap
    				# Title VOBU address map.
