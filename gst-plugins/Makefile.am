# location where plug-ins will be installed
plugindir= $(libdir)/gstreamer-@GST_MAJORMINOR@

plugin_LTLIBRARIES = libgstiec958.la \
		     libgstdvdblocksrc.la \
                     libgstcapsselect.la \
		     libgstcapsaggreg.la \
		     libalsaspdif.la

libgstiec958_la_SOURCES = iec958init.c ac3iec.c ac3_padder.c
libgstiec958_la_CFLAGS = $(GST_CFLAGS)
libgstiec958_la_LDFLAGS = $(GST_LIBS_LIBS)

libgstdvdblocksrc_la_SOURCES = dvdblocksrc.c
libgstdvdblocksrc_la_CFLAGS = $(GST_CFLAGS) $(DVDREAD_CFLAGS)
libgstdvdblocksrc_la_LDFLAGS = $(GST_LIBS_LIBS) $(DVDREAD_LIBS)

libgstcapsselect_la_SOURCES = capsselect.c
libgstcapsselect_la_CFLAGS = $(GST_CFLAGS)
libgstcapsselect_la_LDFLAGS = $(GST_LIBS_LIBS)

libgstcapsaggreg_la_SOURCES = capsaggreg.c
libgstcapsaggreg_la_CFLAGS = $(GST_CFLAGS)
libgstcapsaggreg_la_LDFLAGS = $(GST_LIBS_LIBS)

libalsaspdif_la_SOURCES = alsaspdifinit.c alsaspdifsink.c
libalsaspdif_la_CFLAGS = $(GST_CFLAGS) $(ALSA_CFLAGS) -I$(top_builddir)/../gst-plugins/gst-libs
libalsaspdif_la_LIBADD = $(top_builddir)/../gst-plugins/gst-libs/gst/audio/libgstaudio.la
libalsaspdif_la_LDFLAGS = $(GST_LIBS_LIBS) $(ALSA_LIBS)

noinst_HEADERS = ac3_padder.h ac3iec.h 
