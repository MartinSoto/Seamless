INCLUDES = $(PYTHON_INCLUDES)

pypkgdir = $(pkglibdir)/python/wrapclock

pypkg_LTLIBRARIES = _wrapclockmodule.la

_wrapclockmodule_la_SOURCES = wrapclock.c
_wrapclockmodule_la_CFLAGS = $(GLIB_CFLAGS) $(GST_CFLAGS) $(PYGTK_CFLAGS) \
	-I$(top_builddir)/gst-plugins
_wrapclockmodule_la_LIBADD = $(GLIB_LIBS) $(GST_LIBS)
_wrapclockmodule_la_LDFLAGS = -module -avoid-version \
                              -export-symbols-regex init_wrapclock

pypkg_PYTHON = __init__.py
