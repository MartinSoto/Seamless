import gtk

import gst
import gst.interfaces

class VideoWidget(gtk.DrawingArea):
    def __init__(self):
        gtk.DrawingArea.__init__(self)

        self.connect('realize', self.realizeCb)
        self.connect('size-allocate', self.sizeAllocateCb)
        self.connect('destroy', self.destroyCb)
        
        # Background is always black.
        for state in (gtk.STATE_NORMAL,
                      gtk.STATE_ACTIVE,
                      gtk.STATE_PRELIGHT,
                      gtk.STATE_SELECTED,
                      gtk.STATE_INSENSITIVE):
            self.modify_bg(state, gtk.gdk.color_parse('black'))

        self.videoWin = None
        self.imageSink = None

        self.desiredAspect = 1
        self.eventMask = 0

    def setImageSink(self, imageSink):
        assert isinstance(imageSink, gst.interfaces.XOverlay)
        self.imageSink = imageSink
        self.imageSink.connect('desired-size-changed',
                               self.desiredSizeChanged)

    def getImageSink(self):
        return self.imageSink

    def setEventMask(self, eventMask):
        self.eventMask = eventMask
        if self.window:
            self.window.set_events(gtk.gdk.EXPOSURE_MASK | eventMask)


    #
    # Internal Operations
    #

    def resizeVideo(self):
        if self.window == None:
            return

        allocation = self.get_allocation()
        widgetAspect = float(allocation.width) / allocation.height

        if widgetAspect >= self.desiredAspect:
            width = allocation.height * self.desiredAspect
            height = allocation.height
            x = (allocation.width - width) / 2
            y = 0
        else:
            width = allocation.width
            height = allocation.width / self.desiredAspect
            x = 0
            y = (allocation.height - height) / 2

        if self.videoWin:
            self.videoWin.move_resize(int(x), int(y), int(width), int(height))
        else:
            # Create the video window.
            self.videoWin = gtk.gdk.Window(
                self.window,
                int(width), int(height),
                gtk.gdk.WINDOW_CHILD,
                gtk.gdk.EXPOSURE_MASK,
                gtk.gdk.INPUT_OUTPUT,
                "",
                int(x), int(y))
            self.videoWin.add_filter(self.videoEventFilter)

            self.videoWin.show()


    #
    # Signal Handlers
    #

    def desiredSizeChanged(self, imageSink, width, height):
        self.desiredAspect = float(width) / height
        self.resizeVideo()


    #
    # Callbacks
    #

    def realizeCb(self, widget):
        self.setEventMask(gtk.gdk.EXPOSURE_MASK | self.eventMask)

    def sizeAllocateCb(self, widget, allocation):
        if self.videoWin:
            self.videoWin.resize(allocation.width, allocation.height)
            self.resizeVideo()

    def destroyCb(self, da):
        self.imageSink.set_xwindow_id(0L)

    def videoEventFilter(self, event):
        # FIXME: Check for expose event here. Cannot be done now
        # because pygtk seems to have a bug and only reports "NOTHING"
        # events.
        self.imageSink.set_xwindow_id(self.videoWin.xid)
        return gtk.gdk.FILTER_CONTINUE
