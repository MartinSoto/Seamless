plugin_LTLIBRARIES = libgsta52dec.la

libgsta52dec_la_SOURCES = gsta52dec.c
libgsta52dec_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) \
    $(GSTLIBS_CFLAGS) $(EXTRA_CFLAGS) $(A52DEC_CFLAGS)
libgsta52dec_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS) $(GSTLIBS_LIBS) \
    $(A52DEC_LIBS)
libgsta52dec_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)

noinst_HEADERS = gsta52dec.h
