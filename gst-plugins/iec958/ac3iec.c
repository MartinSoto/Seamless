/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * ac3iec.c: Pad AC3 frames into IEC958 frames for the SP/DIF interface.
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

#include <string.h>

#include <gst/gst.h>

#include "ac3iec.h"


GST_DEBUG_CATEGORY_STATIC (ac3iec_debug);
#define GST_CAT_DEFAULT (ac3iec_debug)


/* The duration of a single IEC958 frame. */
#define IEC958_FRAME_DURATION (32 * GST_MSECOND)


/* ElementFactory information. */
static GstElementDetails ac3iec_details = {
  "AC3 to IEC958 filter",
  "audio/x-ac3",
  "Pads AC3 frames into IEC958 frames suitable for a raw SP/DIF interface",
  "Martin Soto <martinsoto@users.sourceforge.net>"
};


/* AC3IEC signals and args */
enum {
  LAST_SIGNAL,
};

enum {
  ARG_0,
};


static GstStaticPadTemplate ac3iec_sink_template =
GST_STATIC_PAD_TEMPLATE (
  "sink",
  GST_PAD_SINK,
  GST_PAD_ALWAYS,
  GST_STATIC_CAPS (
    "audio/x-ac3"
  )
);

static GstStaticPadTemplate ac3iec_src_template =
GST_STATIC_PAD_TEMPLATE (
  "src",
  GST_PAD_SRC,
  GST_PAD_ALWAYS,
#if 1
  GST_STATIC_CAPS (
    "audio/x-raw-int, "
    "law = (int) 0, "
    "endianness = (int) " G_STRINGIFY (G_LITTLE_ENDIAN) ", "
    "signed = (boolean) true, "
    "width = (int) 16, "
    "depth = (int) 16, "
    "rate = (int) 48000, "
    "channels = (int) 2"
  )
#endif
#if 0
  GST_STATIC_CAPS (
    "audio/x-iec958"
  )
#endif
);


static void	ac3iec_base_init	(gpointer g_class);
static void	ac3iec_class_init   	(AC3IECClass *klass);
static void	ac3iec_init		(AC3IEC *ac3iec);
static void	ac3iec_finalize		(GObject *object);

static void	ac3iec_set_property	(GObject *object,
                                         guint prop_id, 
                                         const GValue *value,
                                         GParamSpec *pspec);
static void	ac3iec_get_property	(GObject *object,
                                         guint prop_id, 
                                         GValue *value,
                                         GParamSpec *pspec);

static gboolean ac3iec_handle_event  	(GstPad *pad, GstEvent *event);
static void	ac3iec_chain		(GstPad *pad, GstData *_data);

static GstElementStateReturn
		ac3iec_change_state	(GstElement *element);


static GstElementClass *parent_class = NULL;
/* static guint ac3iec_signals[LAST_SIGNAL] = { 0 }; */


GType
ac3iec_get_type (void) 
{
  static GType ac3iec_type = 0;

  if (!ac3iec_type) {
    static const GTypeInfo ac3iec_info = {
      sizeof (AC3IECClass),
      ac3iec_base_init,
      NULL,
      (GClassInitFunc)ac3iec_class_init,
      NULL,
      NULL,
      sizeof (AC3IEC),
      0,
      (GInstanceInitFunc)ac3iec_init,
    };
    ac3iec_type = g_type_register_static (GST_TYPE_ELEMENT,
                                          "AC3IEC",
                                          &ac3iec_info, 0);

    GST_DEBUG_CATEGORY_INIT (ac3iec_debug, "ac3iec", 0,
                             "AC3 to IEC958 padding element");
  }
  return ac3iec_type;
}


static void
ac3iec_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &ac3iec_details);
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&ac3iec_sink_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&ac3iec_src_template));
}


static void
ac3iec_class_init (AC3IECClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass*)klass;
  gstelement_class = (GstElementClass*)klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  gobject_class->set_property = ac3iec_set_property;
  gobject_class->get_property = ac3iec_get_property;
  gobject_class->finalize = ac3iec_finalize;

  gstelement_class->change_state = ac3iec_change_state;
}


static void 
ac3iec_init (AC3IEC *ac3iec) 
{
  ac3iec->sink = gst_pad_new_from_template (
                     gst_static_pad_template_get (&ac3iec_sink_template),
                     "sink");
  gst_element_add_pad (GST_ELEMENT (ac3iec), ac3iec->sink);
  gst_pad_set_chain_function (ac3iec->sink, ac3iec_chain);

  GST_FLAG_SET (GST_ELEMENT (ac3iec), GST_ELEMENT_EVENT_AWARE);

  ac3iec->src = gst_pad_new_from_template (
                    gst_static_pad_template_get (&ac3iec_src_template),
                    "src");
  gst_element_add_pad (GST_ELEMENT (ac3iec), ac3iec->src);

  ac3iec->cur_ts = GST_CLOCK_TIME_NONE;

  ac3iec->padder = g_malloc (sizeof(ac3_padder));
  ac3p_init(ac3iec->padder);
}


static void
ac3iec_finalize (GObject *object)
{
  AC3IEC *ac3iec = AC3IEC (object);

  g_free (ac3iec->padder);
}


static void
ac3iec_set_property (GObject *object, guint prop_id,
                     const GValue *value, GParamSpec *pspec)
{
  AC3IEC *ac3iec;

  /* it's not null if we got it, but it might not be ours */
  ac3iec = AC3IEC (object);

  switch (prop_id) {
    default:
      break;
  }
}


static void   
ac3iec_get_property (GObject *object, guint prop_id,
                     GValue *value, GParamSpec *pspec)
{
  AC3IEC *ac3iec;
 
  /* it's not null if we got it, but it might not be ours */
  g_return_if_fail (GST_IS_AC3IEC (object));
 
  ac3iec = AC3IEC (object);
  
  switch (prop_id) {
  default:
    G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    break;
  }
}


static gboolean
ac3iec_handle_event (GstPad *pad, GstEvent *event)
{
  GstEventType type;
  AC3IEC *ac3iec;

  ac3iec = AC3IEC (gst_pad_get_parent (pad));

  type = event ? GST_EVENT_TYPE (event) : GST_EVENT_UNKNOWN;

  switch (type) {

  case GST_EVENT_FLUSH:
    ac3iec->cur_ts = 0;

    /* FIXME: Flush the padder. */
    gst_pad_event_default (pad, event);
    break;

  case GST_EVENT_DISCONTINUOUS:
    {
      GstClockTime time;
	      
      if (gst_event_discont_get_value (event, GST_FORMAT_TIME, &time)) {
        GstEvent *discont;

        GST_DEBUG_OBJECT (ac3iec, "forwarding discontinuity, time %0.3fs",
                          (double) time / GST_SECOND);
        discont = gst_event_new_discontinuous (FALSE, GST_FORMAT_TIME, 
                                               time, NULL);
        gst_pad_push (ac3iec->src, GST_DATA (discont));
      }
    }
    break;

  default:
    gst_pad_event_default (pad, event);
    break;
  }

  return TRUE;
}


static void 
ac3iec_chain (GstPad *pad, GstData *_data)
{
  GstBuffer *buf = GST_BUFFER (_data);
  GstBuffer *new;
  AC3IEC *ac3iec;
  int event;

  g_return_if_fail (pad != NULL);
  g_return_if_fail (GST_IS_PAD (pad));
  g_return_if_fail (buf != NULL);

  ac3iec = AC3IEC (gst_pad_get_parent (pad));

  if (GST_IS_EVENT (buf)) {
    ac3iec_handle_event (pad, GST_EVENT (buf));
    return;
  }

  if (GST_BUFFER_TIMESTAMP (buf) != GST_CLOCK_TIME_NONE) {
    /* Whoever tells me why it is necessary to add a frame in order to
       get synchronized sound will get a beer from me. */
    ac3iec->cur_ts = GST_BUFFER_TIMESTAMP (buf) + IEC958_FRAME_DURATION;
  }

  /* Push the new data into the padder. */
  ac3p_push_data(ac3iec->padder, GST_BUFFER_DATA (buf),
      GST_BUFFER_SIZE (buf));

  /* Parse the data. */
  event = ac3p_parse (ac3iec->padder);
  while (event != AC3P_EVENT_PUSH) {
    if (event == AC3P_EVENT_FRAME) {
      /* We have a new frame: */

      /* Create a new buffer, and copy the frame data into it. */
      new = gst_buffer_new_and_alloc (AC3P_IEC_FRAME_SIZE);
      memcpy (GST_BUFFER_DATA (new), ac3p_frame (ac3iec->padder),
          AC3P_IEC_FRAME_SIZE);

      /* Set the timestamp. */
      GST_BUFFER_TIMESTAMP (new) = ac3iec->cur_ts;
      ac3iec->cur_ts = GST_CLOCK_TIME_NONE;

      /* Push the buffer to the source pad. */
      gst_pad_push (ac3iec->src, GST_DATA (new));
    }

    event = ac3p_parse (ac3iec->padder);
  }

  gst_buffer_unref (buf);
}


static GstElementStateReturn
ac3iec_change_state (GstElement *element)
{
  g_return_val_if_fail (GST_IS_AC3IEC (element), GST_STATE_FAILURE);

  switch (GST_STATE_TRANSITION (element)) {
    case GST_STATE_NULL_TO_READY:
      /* TODO: Initialize padder here?. */
      break;
    case GST_STATE_READY_TO_PAUSED:
      break;
    case GST_STATE_PAUSED_TO_PLAYING:
      break;
    case GST_STATE_PLAYING_TO_PAUSED:
      break;
    case GST_STATE_PAUSED_TO_READY:
      break;
    case GST_STATE_READY_TO_NULL:
      /* TODO: Terminate padder here?. */
      break;
  }

  if (GST_ELEMENT_CLASS (parent_class)->change_state) {
    return GST_ELEMENT_CLASS (parent_class)->change_state (element);
  }

  return GST_STATE_SUCCESS;
}


static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "ac3iec958", GST_RANK_NONE,
                             GST_TYPE_AC3IEC)) {
    return FALSE;
  }

  return TRUE;
}


GST_PLUGIN_DEFINE (
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "iec958",
  "Conversion elements to the iec958 SP/DIF format",
  plugin_init,
  VERSION,
  "LGPL",
  PACKAGE,
  "http://seamless.sourceforge.net");
