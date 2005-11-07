AC_INIT(Seamless DVD Player, 0.1.0)
AC_CONFIG_SRCDIR(src/seamless.py)
AM_INIT_AUTOMAKE(seamless, ${PACKAGE_VERSION})
PACKAGE_TARNAME=$PACKAGE

AC_DEFINE(ORIGIN, "http://seamless.sourceforge.net",
          The origin URL for this package)

AM_CONFIG_HEADER(config.h)

ACLOCAL="$ACLOCAL $ACLOCAL_FLAGS"

dnl libtool
AC_PROG_CC
AC_STDC_HEADERS

AM_DISABLE_STATIC
AC_LIBTOOL_DLOPEN
AM_PROG_LIBTOOL

dnl modify pkg-config path
AC_ARG_WITH(pkg-config-path, 
   AC_HELP_STRING([--with-pkg-config-path],[colon-separated list of pkg-config(1) dirs]),
   [export PKG_CONFIG_PATH=${withval}])

dnl specific additional LDFLAGS for plugins
GST_PLUGIN_LDFLAGS="-module -avoid-version $EXPORT_LDFLAGS"
AC_SUBST(GST_PLUGIN_LDFLAGS, "$GST_PLUGIN_LDFLAGS")

dnl Define plugindir
plugindir="\$(pkglibdir)/gst-plugins"
AC_SUBST(plugindir)

dnl Required versions of dependencies
AC_SUBST(GST_REQ, 0.9.0)
AC_SUBST(GLIB_REQ, 2.0.0)
AC_SUBST(PYGTK_REQ, 2.4.0)

dnl Check for glib2
PKG_CHECK_MODULES(GLIB, glib-2.0 gobject-2.0 gthread-2.0 gmodule-2.0, ,
  AC_MSG_ERROR(You don't have glib-2.0 installed))
AC_SUBST(GLIB_LIBS)
AC_SUBST(GLIB_CFLAGS)

dnl Check for GStreamer
GST_MAJORMINOR=0.9
AC_SUBST(GST_MAJORMINOR)
PKG_CHECK_MODULES(GST, gstreamer-$GST_MAJORMINOR >= $GST_REQ)
AC_SUBST(GST_CFLAGS)
AC_SUBST(GST_LIBS)

AC_SUBST(GST_VERSION_MAJOR)
AC_SUBST(GST_VERSION_MINOR)
AC_SUBST(GST_MAJORMINOR)

dnl Check for Python
AM_PATH_PYTHON
AC_MSG_CHECKING(for python >= 2.4)
prog="
import sys, string
minver = (2,4,0,'final',0)
if sys.version_info < minver:
  sys.exit(1)
sys.exit(0)"

if $PYTHON -c "$prog" 1>&AC_FD_CC 2>&AC_FD_CC
then
  AC_MSG_RESULT(okay)
else
  AC_MSG_ERROR(too old)
fi
AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])

dnl check for PyGTK
PKG_CHECK_MODULES(PYGTK, pygtk-2.0 >= $PYGTK_REQ, ,
  AC_MSG_ERROR(Could not find PyGTK C development files))
AC_SUBST(PYGTK_CFLAGS)

dnl Check for dvdread
AC_CHECK_LIB(dvdread, ifoOpen,
  [AC_SUBST(DVDREAD_LIBS, -ldvdread)],
  [AC_MSG_ERROR(could not find libdvdread libraries)])
AC_CHECK_HEADER(dvdread/dvd_reader.h,
  [AC_SUBST(DVDREAD_CFLAGS,'')],
  [AC_MSG_ERROR(could not find libdvdread headers)])


dnl
dnl Optional Dependencies
dnl

dnl Check for ALSA
AM_PATH_ALSA(0.9.1, HAVE_ALSA="yes", HAVE_ALSA="no")
AC_SUBST(HAVE_ALSA)
AC_SUBST(ALSA_CFLAGS)
AC_SUBST(ALSA_LIBS)
AM_CONDITIONAL(HAVE_ALSA, test "x$HAVE_ALSA" = "xyes")

dnl Check for liba52
AC_CHECK_A52DEC(HAVE_A52DEC="yes", HAVE_A52DEC="no")
AC_SUBST(HAVE_A52DEC)
AC_SUBST(A52DEC_CFLAGS)
AC_SUBST(A52DEC_LIBS)
AM_CONDITIONAL(HAVE_A52DEC, test "x$HAVE_A52DEC" = "xyes")

dnl Check for Pyrex
AC_PATH_PROG(PYREXC, pyrexc, NOT_FOUND)
AC_SUBST(PYREXC)

dnl Be clean and use pure Gtk+-2.0
EXTRA_CFLAGS="-Wall -Werror -DGTK_DISABLE_DEPRECATED=1 -DG_DISABLE_DEPRECATED=1 -DGDK_DISABLE_DEPRECATED=1 -DGDK_PIXBUF_DISABLE_DEPRECATED=1 -DGNOME_DISABLE_DEPRECATED=1 -DGST_DISABLE_DEPRECATED=1"
AC_SUBST(EXTRA_CFLAGS)

AC_OUTPUT([
  Makefile
  config/Makefile
  gst-plugins/Makefile
  gst-plugins/a52dec/Makefile
  gst-plugins/alsaspdif/Makefile
  gst-plugins/capspipe/Makefile
  gst-plugins/dvdblock/Makefile
  gst-plugins/iec958/Makefile
  gst-plugins/mpeg2sub/Makefile
  gst-plugins/mpegstream/Makefile
  gst-plugins/queue/Makefile
  gst-plugins/robustclock/Makefile
  src/Makefile
  src/dvdread/Makefile
  src/machine/Makefile
  src/player/Makefile
  src/wrapclock/Makefile
])

echo
echo "Now type 'make' to compile ${PACKAGE_STRING}."
