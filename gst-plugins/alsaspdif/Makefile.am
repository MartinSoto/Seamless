plugin_LTLIBRARIES = libalsaspdif.la

libalsaspdif_la_SOURCES = alsaspdifsink.c
libalsaspdif_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) \
    $(GSTLIBS_CFLAGS) $(EXTRA_CFLAGS) $(ALSA_CFLAGS)
libalsaspdif_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS) $(GSTLIBS_LIBS) \
    $(ALSA_LIBS)
libalsaspdif_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)

noinst_HEADERS = alsaspdifsink.h
