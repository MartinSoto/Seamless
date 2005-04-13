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

def navEvent(nav):
    """Create and return a nav packet event for the specified nav
    packet."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-nav-packet')
    st.set_value('start_ptm', mpegTimeToGstTime(nav.startTime), 'uint64')
    st.set_value('end_ptm', mpegTimeToGstTime(nav.endTime), 'uint64')
    return gst.event_new_any(st)

def stillFrameEvent():
    """Create and yield a still frame event."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-still-frame')
    yield gst.event_new_any(st)

def audioEvent(physical):
    """Create and yield a new audio event for the specified physical
    stream."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-audio-stream-change')
    st.set_value('physical', physical, 'int')
    yield gst.event_new_any(st)

def subpictureEvent(physical):
    """Create and yield a new subpicture event for the specified
    physical stream."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-stream-change')
    st.set_value('physical', physical, 'int')
    yield gst.event_new_any(st)

def subpictureClutEvent(programChain):
    """Create and yield a new subpicture CLUT event based on the
    specified program chain."""
    st = gst.Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-clut-change')

    # Each value is stored in a separate field.
    for i in range(16):
        st.set_value('clut%02d' % i, programChain.getClutEntry(i + 1))

    yield gst.event_new_any(st)

# def highlightEvent(machine):
#     if machine.highlightArea != None:
#         btnObj = machine.buttonNav.getButton(machine.location.button)
#         (sx, sy, ex, ey) = btnObj.area

#         st = Structure('application/x-gst-dvd');
#         st.set_value('event', 'dvd-spu-highlight')
#         st.set_value('button', machine.location.button)
#         st.set_value('palette', btnObj.paletteSelected)
#         st.set_value('sx', sx)
#         st.set_value('sy', sy)
#         st.set_value('ex', ex)
#         st.set_value('ey', ey)
#     else:
#         st = Structure('application/x-gst-dvd')
#         st.set_value('event', 'dvd-spu-reset-highlight')

#     machine.src.emit('queue-event', event_new_any(st));
