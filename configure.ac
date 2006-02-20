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
AC_SUBST(GST_REQ, 0.9.7)
AC_SUBST(GLIB_REQ, 2.0.0)
AC_SUBST(PYGTK_REQ, 2.4.0)

dnl Check for glib2
PKG_CHECK_MODULES(GLIB, glib-2.0 gobject-2.0 gthread-2.0 gmodule-2.0, ,
  AC_MSG_ERROR(You don't have glib-2.0 installed))
AC_SUBST(GLIB_LIBS)
AC_SUBST(GLIB_CFLAGS)

dnl Check for GStreamer
GST_MAJORMINOR=0.10
AC_SUBST(GST_MAJORMINOR)
PKG_CHECK_MODULES(GST, gstreamer-$GST_MAJORMINOR >= $GST_REQ)
AC_SUBST(GST_CFLAGS)
AC_SUBST(GST_LIBS)

AC_SUBST(GST_VERSION_MAJOR)
AC_SUBST(GST_VERSION_MINOR)
AC_SUBST(GST_MAJORMINOR)

dnl Check for gstreamer-base; uninstalled is selected preferentially
PKG_CHECK_MODULES(GST_BASE, gstreamer-base-$GST_MAJORMINOR >= $GST_REQ,
  HAVE_GST_BASE="yes", HAVE_GST_BASE="no")

if test "x$HAVE_GST_BASE" = "xno"; then
  AC_MSG_ERROR(no GStreamer Base Libs found)
fi

AC_SUBST(GST_BASE_LIBS)
AC_SUBST(GST_BASE_CFLAGS)

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

dnl Check for Pyrex
AC_PATH_PROG(PYREXC, pyrexc, NOT_FOUND)
AC_SUBST(PYREXC)

CFLAGS="-g -O2"
AC_SUBST(CFLAGS)

dnl Make warnings into errors. Use latest glib and GStreamer API.
AM_CFLAGS="-Wall -Werror -DG_DISABLE_DEPRECATED=1 -DGST_DISABLE_DEPRECATED=1"
AC_SUBST([AM_CFLAGS])

AC_OUTPUT([
  Makefile
  config/Makefile
  glade/Makefile
  gst-plugins/Makefile
  gst-plugins/alsaspdif/Makefile
  gst-plugins/capspipe/Makefile
  gst-plugins/seamless/Makefile
  gst-plugins/mpeg2sub/Makefile
  src/Makefile
  src/baseui/Makefile
  src/dvdread/Makefile
  src/gazpacho/Makefile
  src/gazpacho/loader/Makefile
  src/machine/Makefile
  src/player/Makefile
  src/plugin/Makefile
  src/tasklet/Makefile
])

echo
echo "Now type 'make' to compile ${PACKAGE_STRING}."
