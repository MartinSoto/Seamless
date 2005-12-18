plugin_LTLIBRARIES = libdvdblock.la

libdvdblock_la_SOURCES = dvdblocksrc.c
libdvdblock_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) \
    $(GST_BASE_CFLAGS) $(DVDREAD_CFLAGS) $(AM_CFLAGS)
libdvdblock_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS) $(GST_BASE_LIBS) \
    $(DVDREAD_LIBS) 
libdvdblock_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)

noinst_HEADERS = dvdblocksrc.h
