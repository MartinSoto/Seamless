/* Seamless DVD Player
 * Copyright (C) 2003, 2004 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
 * USA
 */


#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <pygobject.h>

#include <gst/gst.h>
#include <gst/gstversion.h>

#include "robustclock/robustclock.h"


static PyObject *gst_module, *gst_clock_type;


static PyObject *
wrap(PyObject *self, PyObject *args)
{
  PyGObject *py_clock;
  GstClock *clock, *robust;

  if (!PyArg_ParseTuple (args, "O!:wrap", gst_clock_type, &py_clock)) {
    return NULL;
  }
  clock = GST_CLOCK(py_clock->obj);

  robust = gst_robust_clock_new (clock);

  return pygobject_new((GObject *) robust);
}


static PyMethodDef wrapclock_methods[] = {
  {"wrap", wrap, METH_VARARGS, "Wrap a gst.Clock into a GstRobustClock."},
  {NULL, NULL, 0, NULL}        /* Sentinel */
};


DL_EXPORT(void)
init_wrapclock (void)
{
  (void) Py_InitModule ("_wrapclock", wrapclock_methods);

  /* Import the Gstreamer module, and retrieve the Clock type. */
  gst_module = PyImport_ImportModule ("gst");
  gst_clock_type = PyObject_GetAttrString (gst_module, "Clock");

  /* Load the wrapper clock library. */
  if (!gst_library_load ("robustclock")) {
    g_warning ("Could not load robustclock library");
  }
}
