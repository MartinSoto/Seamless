INCLUDES = $(PYTHON_INCLUDES)

noinst_LTLIBRARIES = libseamlesselements.la

libseamlesselements_la_SOURCES = plugininit.c ac3iec.c \
    ac3_padder.c dvdblocksrc.c alsaspdifsink.c
libseamlesselements_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) \
    $(GSTLIBS_CFLAGS) $(EXTRA_CFLAGS) $(DVDREAD_CFLAGS) $(ALSA_CFLAGS)
libseamlesselements_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS) $(GSTLIBS_LIBS) \
    $(DVDREAD_LIBS) $(ALSA_LIBS) ../../gst-plugins/gst-libs/gst/audio/libgstaudio.la

noinst_HEADERS = ac3_padder.h ac3iec.h 

#libgstcapsselect_la_SOURCES = capsselect.c
#libgstcapsselect_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) $(EXTRA_CFLAGS)
#libgstcapsselect_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS)

#libgstcapsaggreg_la_SOURCES = capsaggreg.c
#libgstcapsaggreg_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) $(EXTRA_CFLAGS)
#libgstcapsaggreg_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS)

pyexec_LTLIBRARIES = _seamlesspluginmodule.la

_seamlesspluginmodule_la_SOURCES = _seamlessplugin.c
_seamlesspluginmodule_la_CFLAGS = 
_seamlesspluginmodule_la_LDFLAGS = -module -avoid-version \
    -export-symbols-regex . libseamlesselements.la

CLEANFILES = _seamlessplugin.c

_seamlessplugin.c: _seamlessplugin.pyx
	$(PYREXC) _seamlessplugin.pyx
