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

def createCustom(st, outOfBand=False):
    """Create a custom downstream event containing `st`."""
    if outOfBand:
        return gst.event_new_custom(gst.EVENT_CUSTOM_DOWNSTREAM_OOB, st)
    else:
        return gst.event_new_custom(gst.EVENT_CUSTOM_DOWNSTREAM, st)


#
# Standard GStreamer Events
#

def eos():
    """Create and return an end of stream (EOS) event."""
    return gst.event_new_eos()

def filler():
    """Create and return a filler event."""
    return gst.event_new_filler()

def newsegment(update, startTime, endTime):
    """Create and return a newsegment event for the specified start
    and end times. Times are specified in nanoseconds."""
    return gst.event_new_new_segment(update, 1.0, gst.FORMAT_TIME,
                                     startTime, endTime, startTime)


#
# Audio DVD Events
#

def aspectRatioSet(ratio_n, ratio_d):
    """Create and return a new video aspect ratio set event, using the
    specified ratio numerator and denominator."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-video-aspect-set')
    st.set_value('aspect-ratio', gst.Fraction(ratio_n, ratio_d))
    return createCustom(st)


#
# Audio DVD Events
#

def audio(physical):
    """Create and return a new audio event for the specified physical
    stream."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-audio-stream-change')
    st.set_value('physical', physical, 'int')
    return createCustom(st)

def audioFillGap(start, stop):
    """Create and return a new audio fill gap event for the specified
    start and stop times."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-audio-fill-gap')
    st.set_value('start', start, 'uint64')
    st.set_value('stop', stop, 'uint64')
    return createCustom(st)


#
# Subpicture DVD Events
#

def highlight(area, button, palette, immediate=True):
    """Create and return a new highlight event based on the specified
    highlight area, button number, and color palette. If `immediate`
    is True, the event is created as an out-of-band event so that it
    takes affect as soon as possible."""
    (sx, sy, ex, ey) = area

    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-highlight')
    st.set_value('button', button)
    st.set_value('palette', palette)
    st.set_value('sx', sx)
    st.set_value('sy', sy)
    st.set_value('ex', ex)
    st.set_value('ey', ey)

    return createCustom(st, outOfBand=immediate)

def highlightReset():
    """Create and return a new highlight reset event."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-reset-highlight')

    return createCustom(st)

def stillFrame(start, stop):
    """Create and return a still frame event with the specified start
    and stop times."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-still-frame')
    st.set_value('start', start, 'uint64')
    st.set_value('stop', stop, 'uint64')
    return createCustom(st)

def subpictureClut(clut):
    """Create and return a new subpicture CLUT event based on the
    specified color lookup table (an 16 position array)."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-clut-change')

    # Each value is stored in a separate field.
    for i in range(16):
        st.set_value('clut%02d' % i, clut[i])

    return createCustom(st)

def subpicture(physical):
    """Create and return a new subpicture event for the specified
    physical stream."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-stream-change')
    st.set_value('physical', physical, 'int')
    return createCustom(st)

def subpictureHide():
    """Create and return a new subpicture hide event."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-hide')

    return createCustom(st)

def subpictureShow():
    """Create and return a new subpicture show event."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-show')

    return createCustom(st)

def navSequence(number):
    """Create and return a new navigation sequence event with sequence
    number `number`."""
    st = gst.Structure('application/x-gst-dvd')
    st.set_value('event', 'dvd-spu-nav-sequence')
    st.set_value('number', number)

    return createCustom(st)
