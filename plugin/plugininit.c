/* GStreamer
 * Copyright (C) 2003 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * plugininit.c: Seamless private plugin initialization.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 */

#include "config.h"

#include <gst/gst.h>

#include "ac3iec.h"
#include "alsaspdifsink.h"
#include "dvdblocksrc.h"

#include "plugininit.h"


static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "alsaspdifsink", GST_RANK_NONE,
                             GST_TYPE_ALSASPDIFSINK)) {
    return FALSE;
  }

  if (!gst_element_register (plugin, "ac3iec958", GST_RANK_NONE,
                             GST_TYPE_AC3IEC)) {
    return FALSE;
  }

  if (!gst_element_register (plugin, "dvdblocksrc", GST_RANK_NONE,
          GST_TYPE_DVDBLOCKSRC)) {
    return FALSE;
  }

  return TRUE;
}


static GstPluginDesc plugin_desc = {
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "seamless_elements",
  "Private elements for the Seamless DVD Player",
  plugin_init,
  NULL,
  VERSION,
  "GPL",
  PACKAGE,
  "http://seamless.sourceforge.net",
  GST_PADDING_INIT
};


void
seamless_element_init (void)
{
  _gst_plugin_register_static (&plugin_desc);
}
