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

def fillerEvent(machine):
    machine.queueEvent(Event(EVENT_FILLER))

def stillFrameEvent(machine):
    st = Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-still-frame')
    machine.queueEvent(event_new_any(st))
    print >> sys.stderr, 'Still frame set'

def audioEvent(machine):
    st = Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-audio-stream-change')
    st.set_value('physical', machine.audioPhys, 'int')
    machine.queueEvent(event_new_any(st))
    print >> sys.stderr, 'New audio:', machine.audioPhys

def subpictureEvent(machine):
    st = Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-stream-change')
    st.set_value('physical', machine.subpicturePhys, 'int')
    machine.queueEvent(event_new_any(st))
    print >> sys.stderr, 'New subpicture:', machine.subpicturePhys

def subpictureCLUTEvent(machine):
    st = Structure('application/x-gst-dvd');
    st.set_value('event', 'dvd-spu-clut-change')

    # Each value is stored in a separate field.
    for i in range(16):
        st.set_value('clut%02d' % i,
                     machine.highlightProgramChain.getCLUTEntry(i + 1))

    machine.queueEvent(event_new_any(st))

def highlightEvent(machine):
    if machine.highlightArea != None:
        btnObj = machine.buttonNav.getButton(machine.location.button)
        (sx, sy, ex, ey) = btnObj.area

        st = Structure('application/x-gst-dvd');
        st.set_value('event', 'dvd-spu-highlight')
        st.set_value('button', machine.location.button)
        st.set_value('palette', btnObj.paletteSelected)
        st.set_value('sx', sx)
        st.set_value('sy', sy)
        st.set_value('ex', ex)
        st.set_value('ey', ey)
    else:
        st = Structure('application/x-gst-dvd')
        st.set_value('event', 'dvd-spu-reset-highlight')

    machine.src.emit('queue-event', event_new_any(st));
