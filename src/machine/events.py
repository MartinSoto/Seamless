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

import gst

import dvdread


def mpegTimeToGstTime(mpegTime):
    """Convert MPEG time values to the GStreamer time format."""
    return (long(mpegTime) * gst.MSECOND) / 90

def navEvent(nav):
    """Create and return a nav packet event for the specified nav
    packet."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-nav-packet')
    st.set_value('start_ptm', mpegTimeToGstTime(nav.startTime), 'uint64')
    st.set_value('end_ptm', mpegTimeToGstTime(nav.endTime), 'uint64')
    return gst.event_new_any(st)

def stillFrameEvent():
    """Create and return a still frame event."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-still-frame')
    return gst.event_new_any(st)

def audioEvent(physical):
    """Create and return a new audio event for the specified physical
    stream."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-audio-stream-change')
    st.set_value('physical', physical, 'int')
    return gst.event_new_any(st)

def subpictureEvent(physical):
    """Create and return a new subpicture event for the specified
    physical stream."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-stream-change')
    st.set_value('physical', physical, 'int')
    return gst.event_new_any(st)

def subpictureClutEvent(programChain):
    """Create and return a new subpicture CLUT event based on the
    specified program chain."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-clut-change')

    # Each value is stored in a separate field.
    for i in range(16):
        st.set_value('clut%02d' % i, programChain.getClutEntry(i + 1))

    return gst.event_new_any(st)

def highlightEvent(nav, button):
    """Create and return a new highlight event based on the specified
    navigation packet and button number."""
    if nav == None or \
       nav.highlightStatus == dvdread.HLSTATUS_NONE or \
       not 1 <= button <= nav.buttonCount:
        print "+++ Deactivating highlight"
        # No highlight button.
        st = gst.Structure('application/x-gst-dvd')
        st.set_value('event', 'dvd-spu-reset-highlight')
    else:
        btnObj = nav.getButton(button)
        (sx, sy, ex, ey) = btnObj.area
        print "+++ Activating highlight", btnObj.area

        st = gst.Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-highlight')
        st.set_value('button', button)
        st.set_value('palette', btnObj.paletteSelected)
        st.set_value('sx', sx)
        st.set_value('sy', sy)
        st.set_value('ex', ex)
        st.set_value('ey', ey)

    return gst.event_new_any(st)

def flushEvent():
    """Create and return a flush event."""
    return gst.Event(gst.EVENT_FLUSH)
