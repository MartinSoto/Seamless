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


def mpegTimeToGstTime(mpegTime):
    """Convert MPEG time values to the GStreamer time format."""
    return (long(mpegTime) * gst.MSECOND) / 90

def audio(physical):
    """Create and return a new audio event for the specified physical
    stream."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-audio-stream-change')
    st.set_value('physical', physical, 'int')
    return gst.event_new_any(st)

def eos():
    """Create and return an end of stream (EOS) event."""
    return gst.Event(gst.EVENT_EOS)

def filler():
    """Create and return a filler event."""
    return gst.Event(gst.EVENT_FILLER)

def flush():
    """Create and return a flush event."""
    return gst.Event(gst.EVENT_FLUSH)

def highlight(area, button, palette):
    """Create and return a new highlight event based on the specified
    highlight area, button number, and color palette."""
    (sx, sy, ex, ey) = area

    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-highlight')
    st.set_value('button', button)
    st.set_value('palette', palette)
    st.set_value('sx', sx)
    st.set_value('sy', sy)
    st.set_value('ex', ex)
    st.set_value('ey', ey)

    return gst.event_new_any(st)

def highlightReset():
    """Create and return a new highlight reset event."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-reset-highlight')

    return gst.event_new_any(st)

def nav(startTime, endTime):
    """Create and return a nav packet event for the specified start
    and end times."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-nav-packet')
    st.set_value('start_ptm', mpegTimeToGstTime(startTime), 'uint64')
    st.set_value('end_ptm', mpegTimeToGstTime(endTime), 'uint64')
    return gst.event_new_any(st)

def stillFrame():
    """Create and return a still frame event."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-still-frame')
    return gst.event_new_any(st)

def subpictureClut(clut):
    """Create and return a new subpicture CLUT event based on the
    specified color lookup table (an 16 position array)."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-clut-change')

    # Each value is stored in a separate field.
    for i in range(16):
        st.set_value('clut%02d' % i, clut[i])

    return gst.event_new_any(st)

def subpicture(physical):
    """Create and return a new subpicture event for the specified
    physical stream."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-stream-change')
    st.set_value('physical', physical, 'int')
    return gst.event_new_any(st)

def subpictureHide():
    """Create and return a new subpicture hide event."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-hide')

    return gst.event_new_any(st)

def subpictureShow():
    """Create and return a new subpicture show event."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-show')

    return gst.event_new_any(st)

