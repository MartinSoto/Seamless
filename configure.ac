AC_PREREQ(2.57)
AC_INIT
AC_CANONICAL_TARGET

PACKAGE=seamless
VERSION=0.0.1

dnl These AC_DEFINE_UNQUOTED's are necessary for make dist to work
AC_DEFINE_UNQUOTED(PACKAGE, "$PACKAGE")
AC_DEFINE_UNQUOTED(VERSION, "$VERSION")
AC_DEFINE_UNQUOTED(RELEASE, "$RELEASE")
AC_SUBST(PACKAGE)
AC_SUBST(VERSION)
AC_SUBST(RELEASE)

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)

AC_PROG_CC

AC_DISABLE_STATIC
AC_PROG_LIBTOOL

dnl Check for pkgconfig first
AC_CHECK_PROG(HAVE_PKGCONFIG, pkg-config, yes, no)

dnl Give error and exit if we don't have pkgconfig
if test "x$HAVE_PKGCONFIG" = "xno"; then
  AC_MSG_ERROR(You need to have pkgconfig installed!)
fi

dnl Now we're ready to ask for gstreamer libs and cflags
dnl And we can also ask for the right version of gstreamer
GST_REQUIRED=0.8.0

dnl Check for gstreamer 0.8
GST_MAJORMINOR=0.8
PKG_CHECK_MODULES(GST, \
  gstreamer-$GST_MAJORMINOR >= $GST_REQUIRED \
  gstreamer-control-$GST_MAJORMINOR >= $GST_REQUIRED,
  HAVE_GST=yes,HAVE_GST=no)

if test "x$HAVE_GST" = "xno"; then
  AC_MSG_ERROR(You need GStreamer development packages installed!)
fi

dnl Make GST_CFLAGS and GST_LIBS available
AC_SUBST(GST_CFLAGS)
AC_SUBST(GST_LIBS)

dnl Make GST_MAJORMINOR available in Makefile.am
AC_SUBST(GST_MAJORMINOR)

dnl If we need them, we can also use the plugin libraries
PKG_CHECK_MODULES(GST_LIBS, gstreamer-libs-$GST_MAJORMINOR >= $GST_REQUIRED,
                  HAVE_GST_LIBS=yes, HAVE_GST_LIBS=no)

dnl Give a warning if we don't have gstreamer libs
if test "x$HAVE_GST_LIBS" = "xno"; then
  AC_MSG_NOTICE(no GStreamer plugin libs found)
fi

dnl Make GST_LIBS_CFLAGS and GST_LIBS_LIBS available
AC_SUBST(GST_LIBS_CFLAGS)
AC_SUBST(GST_LIBS_LIBS)

dnl check for glib
AM_PATH_GLIB_2_0(2.2.0,,[AC_MSG_ERROR(You need GLIB 2.2 or newer to compile Seamless)],gthread)

dnl Check for python
AM_PATH_PYTHON
AC_MSG_CHECKING(for python >= 2.2)
prog="
import sys, string
minver = (2,2,0,'final',0)
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

dnl Check for ALSA
AM_PATH_ALSA(0.9.1)
AC_SUBST(ALSA_CFLAGS)
AC_SUBST(ALSA_LIBS)

dnl Check for dvdread
AC_CHECK_LIB(dvdread, ifoOpen,
  [AC_SUBST(DVDREAD_LIBS, -ldvdread)],
  [AC_MSG_ERROR(could not find libdvdread libraries)])
AC_CHECK_HEADER(dvdread/dvd_reader.h,
  [AC_SUBST(DVDREAD_CFLAGS,'')],
  [AC_MSG_ERROR(could not find libdvdread headers)])

dnl Check for Pyrex
AC_PATH_PROG(PYREXC, pyrexc, NOT_FOUND)
if test $PYREXC = NOT_FOUND
then
  AC_MSG_ERROR(could not find Pyrex compiler)
fi
AC_SUBST(PYREXC)

dnl Add debugging options
changequote(,)dnl
if test "x$GCC" = xyes; then
  case " $CFLAGS " in
  *[\	\ ]-Wall[\	\ ]*) ;;
  *) CFLAGS="$CFLAGS -Wall" ;;
  esac
fi
changequote([,])dnl

AC_OUTPUT([
  Makefile
  gst-plugins/Makefile
  dvdread/Makefile
])
