plugin_LTLIBRARIES = libcapspipe.la

libcapspipe_la_SOURCES = capsselect.c capsaggreg.c capspipeinit.c
libcapspipe_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) $(EXTRA_CFLAGS)
libcapspipe_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS)
libcapspipe_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)

noinst_HEADERS = capsselect.h capsaggreg.h
