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

"""A number of factory methods that create command objects used to
represent the operations that the virtual machine can do on a
pipeline."""

def playVobu(domain, titleNr, sectorNr):
    """Play the VOBU corresponding to 'domain', 'titleNr', and
    'sectorNr'."""
    def op(pipeline):
        pipeline.playVobu(domain, titleNr, sectorNr)

    return op

def setAudio(phys):
    """Set the physical audio stream to 'phys'."""
    def op(pipeline):
        pipeline.setAudio(phys)

    return op

def setSubpicture(phys):
    """Set the physical subpicture stream to 'phys'."""
    def op(pipeline):
        pipeline.setSubpicture(phys)

    return op

def setSubpictureClut(clut):
    """Set the subpicture color lookup table to 'clut'.

    'clut' is a 16-position array."""
    def op(pipeline):
        pipeline.setSubpictureClut(clut)

    return op

def highlight(area, button, palette):
    """Highlight the specified area, corresponding to the
    specified button number and using the specified palette."""
    def op(pipeline):
        pipeline.highlight(area, button, palette)

    return op

def resetHighlight():
    """Clear (reset) the highlighted area."""
    def op(pipeline):
        pipeline.resetHighlight()

    return op

def stillFrame():
    """Tell the pipeline that a still frame was sent."""
    def op(pipeline):
        pipeline.stillFrame()

    return op

def flush():
    """Flush the pipeline."""
    def op(pipeline):
        pipeline.flush()

    return op

def pause():
    """Pause the pipeline for a short time (currently 0.1s)."""
    def op(pipeline):
        pipeline.pause()

    return op
