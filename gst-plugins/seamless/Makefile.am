plugin_LTLIBRARIES = libseamless.la

libseamless_la_SOURCES = seamlessinit.c dvdaspect.c dvdblocksrc.c
libseamless_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) \
    $(GST_BASE_CFLAGS) $(DVDREAD_CFLAGS) $(AM_CFLAGS)
libseamless_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS) $(GST_BASE_LIBS) \
    $(DVDREAD_LIBS) 
libseamless_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)

noinst_HEADERS = dvdaspect.h dvdblocksrc.h
