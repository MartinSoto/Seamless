/* Seamless
 * Copyright (C) 2004-2006 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * seamlessinit.c: Initialization for the Seamless specific
 * GStreamer plugin.
 * 
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "audiofiller.h"
#include "dvdaspect.h"
#include "dvdblocksrc.h"


static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "audiofiller", GST_RANK_NONE,
          GST_TYPE_AUDIOFILLER)) {
    return FALSE;
  }
  if (!gst_element_register (plugin, "dvdaspect", GST_RANK_NONE,
          GST_TYPE_DVDASPECT)) {
    return FALSE;
  }
  if (!gst_element_register (plugin, "dvdblocksrc", GST_RANK_NONE,
          GST_TYPE_DVDBLOCKSRC)) {
    return FALSE;
  }

  return TRUE;
}


GST_PLUGIN_DEFINE (
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "seamless",
  "Special elements for the Seamless DVD player",
  plugin_init,
  VERSION,
  "GPL",
  PACKAGE,
  "http://seamless.sourceforge.net");
