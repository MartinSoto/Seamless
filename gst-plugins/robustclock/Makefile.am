plugin_LTLIBRARIES = librobustclock.la

librobustclock_la_SOURCES = robustclock.c
librobustclock_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) $(EXTRA_CFLAGS)
librobustclock_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS)
librobustclock_la_LDFLAGS = $(GST_PLUGIN_LDFLAGS)

noinst_HEADERS = robustclock.h
