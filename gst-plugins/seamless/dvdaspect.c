/* Seamless DVD Player
 * Copyright (C) 2005-2006 Martin Soto <martinsoto@users.sourceforge.net>
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

#include <string.h>

#include "dvdaspect.h"


GST_DEBUG_CATEGORY_STATIC (dvdaspect_debug);
#define GST_CAT_DEFAULT (dvdaspect_debug)


/* ElementFactory information. */
static GstElementDetails dvdaspect_details = GST_ELEMENT_DETAILS (
  "DVD aspect ratio correction element",
  "",
  "Corrects video aspect ratio values based on DVD events",
  "Martin Soto <martinsoto@users.sourceforge.net>");


/* DVDAspect signals and properties. */
enum {
  LAST_SIGNAL,
};

enum {
  PROP_0,
};


static GstStaticPadTemplate dvdaspect_sink_template =
    GST_STATIC_PAD_TEMPLATE ("sink",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/x-raw-rgb, "
        "framerate = (fraction) [ 0, MAX ], "
        "width = (int) [ 1, MAX ], "
        "height = (int) [ 1, MAX ]; "
        "video/x-raw-yuv, "
        "framerate = (fraction) [ 0, MAX ], "
        "width = (int) [ 1, MAX ], "
	"height = (int) [ 1, MAX ]")
    );

static GstStaticPadTemplate dvdaspect_src_template =
    GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/x-raw-rgb, "
        "framerate = (fraction) [ 0, MAX ], "
        "width = (int) [ 1, MAX ], "
        "height = (int) [ 1, MAX ]; "
        "video/x-raw-yuv, "
        "framerate = (fraction) [ 0, MAX ], "
        "width = (int) [ 1, MAX ], "
	"height = (int) [ 1, MAX ]")
    );


#define _do_init(bla) \
    GST_DEBUG_CATEGORY_INIT (dvdaspect_debug, "dvdaspect", 0, \
        "DVD aspect ratio correction element");

GST_BOILERPLATE_FULL (DVDAspect, dvdaspect, GstBaseTransform,
    GST_TYPE_BASE_TRANSFORM, _do_init);

static void
dvdaspect_base_init(gpointer g_class);
static void
dvdaspect_class_init (DVDAspectClass *klass);
static void 
dvdaspect_init (DVDAspect * dvdaspect, DVDAspectClass * klass);
static void
dvdaspect_finalize (GObject *object);

static void
dvdaspect_set_property (GObject *object, guint prop_id, const GValue *value,
    GParamSpec *pspec);
static void
dvdaspect_get_property (GObject *object, guint prop_id, GValue *value,
    GParamSpec *pspec);

static gboolean
dvdaspect_update_src_caps (DVDAspect * dvdaspect);

static gboolean
dvdaspect_event (GstBaseTransform *trans, GstEvent *event);
static GstFlowReturn
dvdaspect_transform_ip (GstBaseTransform *trans, GstBuffer *buf);
static GstFlowReturn 
dvdaspect_prepare_output_buffer (GstBaseTransform * trans,
    GstBuffer *input, gint size, GstCaps *caps, GstBuffer **buf);


/* static guint dvdaspect_signals[LAST_SIGNAL] = { 0 }; */


static void
dvdaspect_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &dvdaspect_details);
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&dvdaspect_src_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&dvdaspect_sink_template));
}


static void
dvdaspect_class_init (DVDAspectClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;
  GstBaseTransformClass *gstbase_transform_class;

  gobject_class = G_OBJECT_CLASS (klass);
  gstelement_class = GST_ELEMENT_CLASS (klass);
  gstbase_transform_class = (GstBaseTransformClass *) klass;

  parent_class = g_type_class_ref (GST_TYPE_BASE_TRANSFORM);

  gobject_class->set_property = dvdaspect_set_property;
  gobject_class->get_property = dvdaspect_get_property;
  gobject_class->finalize = dvdaspect_finalize;

  gstbase_transform_class->event = dvdaspect_event;
  gstbase_transform_class->transform_ip = dvdaspect_transform_ip;
  gstbase_transform_class->prepare_output_buffer =
    dvdaspect_prepare_output_buffer;
}


static void 
dvdaspect_init (DVDAspect * dvdaspect, DVDAspectClass * klass)
{
  gst_base_transform_set_in_place (GST_BASE_TRANSFORM (dvdaspect), TRUE);

  /* Set the current caps to arbitrary fixed caps. They will be
     replaced as soon as the element goes to the PLAYING state,
     anyway. */
  dvdaspect->sink_caps = gst_caps_new_simple ("video/x-raw-rgb", NULL);
  dvdaspect->src_caps = gst_caps_new_simple ("video/x-raw-rgb", NULL);

  dvdaspect->aspect_d = 0;
}


static void
dvdaspect_finalize (GObject *object)
{
  DVDAspect *dvdaspect = DVDASPECT (object);

  gst_caps_unref (dvdaspect->sink_caps);
  gst_caps_unref (dvdaspect->src_caps);
}


static void
dvdaspect_set_property (GObject *object, guint prop_id,
    const GValue *value, GParamSpec *pspec)
{
  /* DVDAspect *dvdaspect = DVDASPECT (object); */

  g_return_if_fail (GST_IS_DVDASPECT (object));
 
  switch (prop_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static void   
dvdaspect_get_property (GObject *object, guint prop_id,
    GValue *value, GParamSpec *pspec)
{
  DVDAspect *dvdaspect;
 
  g_return_if_fail (GST_IS_DVDASPECT (object));
 
  dvdaspect = DVDASPECT (object);
  
  switch (prop_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static gboolean
dvdaspect_update_src_caps (DVDAspect * dvdaspect)
{
  GstStructure *structure;
  gint width, height;
  gint par_n, par_d;

  if (dvdaspect->aspect_d != 0) {
    /* We have to force a certain aspect ratio: */

    /* Obtain width and height from the source caps. */
    structure = gst_caps_get_structure (dvdaspect->sink_caps, 0);
    if (!gst_structure_get_int (structure, "width", &width) ||
	!gst_structure_get_int (structure, "height", &height)) {
      return FALSE;
    }

    /* Calculate the forced pixel aspect ratio. */
    par_n = height * dvdaspect->aspect_n;
    par_d = width * dvdaspect->aspect_d;

    GST_DEBUG_OBJECT (dvdaspect,
	"updating src caps w: %d, h: %d, desired aspect: %d/%d, "
	"pixel aspect: %d/%d", width, height, dvdaspect->aspect_n,
	dvdaspect->aspect_d, par_n, par_d);

    /* Source caps are a copy of the sink caps, with a possibly
       different pixel aspect ratio. */
    structure = gst_structure_copy (structure);
    gst_structure_set (structure, "pixel-aspect-ratio", GST_TYPE_FRACTION,
	par_n, par_d, NULL);
    gst_caps_replace (&(dvdaspect->src_caps),
	gst_caps_new_full (structure, NULL));
  } else {
    /* Source caps are identical to sink caps. */
    gst_caps_replace (&(dvdaspect->src_caps), dvdaspect->sink_caps);
  }

  return TRUE;
}


static gboolean
dvdaspect_event (GstBaseTransform *trans, GstEvent *event)
{
  gboolean res = TRUE;
  DVDAspect *dvdaspect = DVDASPECT (trans);

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_CUSTOM_DOWNSTREAM:
    {
      const GstStructure *structure = gst_event_get_structure (event);
      const char *event_type;

      if (!gst_structure_has_name (structure, "application/x-gst-dvd")) {
	break;
      }

      event_type = gst_structure_get_string (structure, "event");

      if (strcmp (event_type, "dvd-video-aspect-set") == 0) {
	if (!gst_structure_get_fraction (structure, "aspect-ratio",
		&(dvdaspect->aspect_n), &(dvdaspect->aspect_d))) {
	  GST_WARNING_OBJECT (dvdaspect,
	      "aspect-set event received without aspect-ratio field");
	  res = FALSE;
	  goto done;
	}

	GST_DEBUG_OBJECT (dvdaspect, "new forced aspect ratio, w: %d, h: %d",
	    dvdaspect->aspect_n, dvdaspect->aspect_d);

	res = dvdaspect_update_src_caps (dvdaspect);
      }

      break;
    }

    default:
      break;
  }

 done:
  return res;
}


static GstFlowReturn
dvdaspect_transform_ip (GstBaseTransform *trans, GstBuffer *buf)
{
  return GST_FLOW_OK;
}


static GstFlowReturn 
dvdaspect_prepare_output_buffer (GstBaseTransform * trans,
    GstBuffer *input, gint size, GstCaps *caps, GstBuffer **buf)
{
  DVDAspect *dvdaspect = DVDASPECT (trans);

  if (!gst_caps_is_equal_fixed (dvdaspect->sink_caps, caps)) {
    /* We have new caps in the sink pad. */
    gst_caps_replace (&(dvdaspect->sink_caps), caps);
    if (!dvdaspect_update_src_caps (dvdaspect)) {
      return GST_FLOW_ERROR;
    }
  }

  /* In order to be able to modify the caps, we create a subbuffer
     with the same size. */
  *buf = gst_buffer_create_sub (input, 0, size);
  GST_BUFFER_DURATION (buf) = GST_BUFFER_DURATION (input);
  GST_BUFFER_OFFSET_END (buf) = GST_BUFFER_OFFSET_END (input);
  gst_buffer_set_caps (*buf, dvdaspect->src_caps);

  return GST_FLOW_OK;
}

