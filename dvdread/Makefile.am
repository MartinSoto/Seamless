INCLUDES = $(PYTHON_INCLUDES)

pyexec_LTLIBRARIES = _dvdreadmodule.la

_dvdreadmodule_la_SOURCES = _dvdread.c
_dvdreadmodule_la_CFLAGS = $(DVDREAD_CFLAGS)
_dvdreadmodule_la_LDFLAGS = $(DVDREAD_LIBS) -module -avoid-version \
			    -export-symbols-regex .

CLEANFILES = _dvdread.c

_dvdread.c: _dvdread.pyx ifo_types.pyx nav_types.pyx
	$(PYREXC) _dvdread.pyx
