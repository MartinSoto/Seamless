# -*- Python -*-
# Seamless DVD Player
# Copyright (C) 2004 Martin Soto <soto@users.sourceforge.net>
# This file Copyright (C) 2000, 2001, 2002
#    Håkan Hjort <d95hjort@dtek.chalmers.se>
#
# The data structures in this file should represent the layout of the
# pci and dsi packets as they are stored in the stream.  Information
# found by reading the source to VOBDUMP is the base for the structure
# and names of these data types.
#
# VOBDUMP: a program for examining DVD .VOB files.
# Copyright 1998, 1999 Eric Smith <eric@brouhaha.com>
#
# VOBDUMP is free software you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.  Note that I am not
# granting permission to redistribute or modify VOBDUMP under the terms
# of any later version of the General Public License.
#
# This program is distributed in the hope that it will be useful (or at
# least amusing), but WITHOUT ANY WARRANTY without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307
# USA

cdef extern from "dvdread/nav_types.h":
    # PCI General Information
    ctypedef struct pci_gi_t:
        uint32_t nv_pck_lbn	# sector address of this nav pack
        uint16_t vobu_cat	# 'category' of vobu
        user_ops_t vobu_uop_ctl	# UOP of vobu
        uint32_t vobu_s_ptm	# start presentation time of vobu
        uint32_t vobu_e_ptm	# end presentation time of vobu
        uint32_t vobu_se_e_ptm	# end ptm of sequence end in vobu
        dvd_time_t e_eltm	# Cell elapsed time
        char vobu_isrc[32]

    # Non Seamless Angle Information
    ctypedef struct nsml_agli_t:
        uint32_t nsml_agl_dsta[9]
				# address of destination vobu in AGL_C#n

    # Highlight General Information
    # For btngrX_dsp_ty the bits have the following meaning:
    # 000b: normal 4/3 only buttons
    # XX1b: wide (16/9) buttons
    # X1Xb: letterbox buttons
    # 1XXb: pan & scan buttons
    ctypedef struct hl_gi_t:
        uint16_t hli_ss		# status, only low 2 bits 0: no buttons,
        			# 1: different 2: equal 3: equal except
                                # for button cmds
        uint32_t hli_s_ptm	# start ptm of hli
        uint32_t hli_e_ptm	# end ptm of hli
        uint32_t btn_se_e_ptm	# end ptm of button select

        unsigned int btngr1_dsp_ty
        			# Button group 1 type
        unsigned int btngr_ns	# Number of button groups <= 3
        unsigned int btngr3_dsp_ty
        			# Button group 3 type
        unsigned int btngr2_dsp_ty
        			# Button group 2 type

        uint8_t btn_ofn		# button offset number range 0-255
        uint8_t btn_ns		# number of valid buttons <= 36/18/12
        			# (low 6 bits)
        uint8_t nsl_btn_ns	# number of numerically selectable buttons
        			# (low 6 bits) nsl_btn_ns <= btn_ns
        uint8_t fosl_btnn	# forcedly selected button (low 6 bits)
        uint8_t foac_btnn	# forcedly activated button (low 6 bits)

    # Button Color Information Table
    # Each entry is a 32bit word that contains the color indexes and alpha
    # values to use.  They are all represented as 4 bit numbers and stored
    # in the following pattern [Ci3, Ci2, Ci1, Ci0, A3, A2, A1, A0].
    # The actual palette that the indexes refer to is in the PGC.
    ctypedef struct btn_colit_t:
        uint32_t btn_coli[3][2]	# [button color number-1][select:0/action:1]

    # Button Information
    ctypedef struct btni_t:
        unsigned int btn_coln	# button color number
        unsigned int x_start	# x start offset within the overlay
        unsigned int x_end	# x end offset within the overlay

        unsigned int up		# button index when pressing up

        unsigned int auto_action_mode
        			# 0: no, 1: activated if selected
        unsigned int y_start	# y start offset within the overlay
        unsigned int y_end	# y end offset within the overlay

        unsigned int down	# button index when pressing down
        unsigned int left	# button index when pressing left
        unsigned int right	# button index when pressing right

        vm_cmd_t cmd		# Button command

    # Highlight Information
    ctypedef struct hli_t:
        hl_gi_t hl_gi
        btn_colit_t btn_colit
        btni_t btnit[36]

    # PCI packet
    ctypedef struct pci_t:
        pci_gi_t pci_gi
        nsml_agli_t nsml_agli
        hli_t hli

    # DSI General Information
    ctypedef struct dsi_gi_t:
        uint32_t nv_pck_scr
        uint32_t nv_pck_lbn	# sector address of this nav pack
        uint32_t vobu_ea	# end address of this VOBU
        uint32_t vobu_1stref_ea	# end address of the 1st reference image
        uint32_t vobu_2ndref_ea	# end address of the 2nd reference image
        uint32_t vobu_3rdref_ea	# end address of the 3rd reference image
        uint16_t vobu_vob_idn	# VOB Id number that this VOBU is part of
        uint8_t vobu_c_idn	# Cell Id number that this VOBU is part of
        dvd_time_t c_eltm	# Cell elapsed time

    # Seamless angle (???)
    ctypedef struct vob_a_t:
        uint32_t stp_ptm1
        uint32_t stp_ptm2
        uint32_t gap_len1
        uint32_t gap_len2

    # Seamless Playback Information
    ctypedef struct sml_pbi_t:
        uint16_t category	# 'category' of seamless VOBU
        uint32_t ilvu_ea	# Relative offset to the last sector
                                # of the current interleaved unit.
        uint32_t ilvu_sa	# Relative offset to the first sector
                                # of the next interleaved unit.
        uint16_t size		# Size of next interleaved unit.
        uint32_t vob_v_s_s_ptm	# video start ptm in vob
        uint32_t vob_v_e_e_ptm	# video end ptm in vob
        vob_a_t vob_a[8]

    # Seamless Angle Information for one angle
    ctypedef struct sml_agl_data_t:
        uint32_t address	# offset to next ILVU, high bit is before/after
        uint16_t size		# byte size of the ILVU pointed to by address

    # Seamless Angle Information
    ctypedef struct sml_agli_t:
        sml_agl_data_t data[9]

    # VOBU Search Information
    ctypedef struct vobu_sri_t:
        uint32_t next_video	# Next vobu that contains video
        uint32_t fwda[19]	# Forwards, time
        uint32_t next_vobu
        uint32_t prev_vobu
        uint32_t bwda[19]	# Backwards, time
        uint32_t prev_video

    # Synchronous Information
    ctypedef struct synci_t:
        uint16_t a_synca[8]	# offset to first audio packet for this VOBU
        uint32_t sp_synca[32]	# offset to first subpicture packet

    # DSI packet
    ctypedef struct dsi_t:
        dsi_gi_t dsi_gi
        sml_pbi_t sml_pbi
        sml_agli_t sml_agli
        vobu_sri_t vobu_sri
        synci_t synci
