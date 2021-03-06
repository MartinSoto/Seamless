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

"""Command objects to control the playback pipeline.

Any virtual machine implementation must return intances of the classes
in this module."""

class PipelineCmd(object):
    """A generic command object.

    Objects of this class, when invoked with a pipeline object as
    parameter, call the method named by attribute `methodName` passing
    it the paremeters received by the object constructor."""
    __slots__ = ('args',
                 'keywords')

    def __init__(self, *args, **keywords):
        self.args = args
        self.keywords = keywords

    methodName = None

    def __call__(self, pipeline):
        getattr(pipeline, self.methodName)(*self.args, **self.keywords)


class DoNothing(PipelineCmd):
    """A do-nothing command object."""
    __slots__ = ()

    def __call__(self, pipeline):
        pass


class PlayVobu(PipelineCmd):
    """When constructed with parameter list `(domain, titleNr,
    sectorNr)`, play the VOBU corresponding to domain `domain`, title
    number `titleNr`, and sector number `sectorNr`."""
    __slots__ = ()
    methodName = 'playVobu'


class CancelVobu(PipelineCmd):
    """When constructed without parameters, cancel the effect of the
    last `PlayVobu` operation. A new `PlayVobu` must be sent
    afterwards in order for the pipeline to be able to resume
    playback."""
    __slots__ = ()
    methodName = 'cancelVobu'


# Since accepting the playback of a VOBU is the default, `acceptVobu`
# is equivalent to doing nothing.
class AcceptVobu(DoNothing):
    pass


ASPECT_RATIO_4_3 = 10
ASPECT_RATIO_16_9 = 11

class SetAspectRatio(PipelineCmd):
    """When constructed with parameter list `(aspectRatio)`, set the
    aspect ratio to the one specified. `aspectRatio` must be one of
    the `ASPECT_RATIO` constants in this module."""
    __slots__ = ()
    methodName = 'setAspectRatio'


class SetAudio(PipelineCmd):
    """When constructed with parameter list `(phys)`, set the physical
    audio stream to 'phys'."""
    __slots__ = ()
    methodName = 'setAudio'


class SetSubpicture(PipelineCmd):
    """When constructed with parameter list `(phys, hide)`, set the
    physical subpicture stream to `phys` and hide it if `hide` is
    `True`."""
    __slots__ = ()
    methodName = 'setSubpicture'


class SetSubpictureClut(PipelineCmd):
    """When constructed with parameter list `(clut)`, set the
    subpicture color lookup table to 'clut''clut' is a 16-position
    array."""
    __slots__ = ()
    methodName = 'setSubpictureClut'


class Highlight(PipelineCmd):
    """When constructed with parameter list `(area, button, palette)`,
    highlight the specified area, corresponding to the specified
    button number and using the specified palette."""
    __slots__ = ()
    methodName = 'highlight'


class ResetHighlight(PipelineCmd):
    """When constructed without parameters, clear (reset) the highlighted
    area."""
    __slots__ = ()
    methodName = 'resetHighlight'


class StillFrame(PipelineCmd):
    """When constructed without parameter list `(seconds)', tell the
    pipeline that a still frame was sent and should be displayed for
    the specified number of seconds. If `seconds` is None the still
    frame should remain displayed until an external event, like user
    interaction, cancels it."""
    __slots__ = ()
    methodName = 'stillFrame'
