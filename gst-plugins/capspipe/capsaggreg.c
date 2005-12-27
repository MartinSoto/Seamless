/* GStreamer
 * Copyright (C) 2004-2005 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * capsaggreg.c: Aggregate contents from multiple sink pads into a 
 *               single source, negotiating capabilities as needed.
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

#include <string.h>

#include "config.h"
#include "capsaggreg.h"


#ifndef __GST_DISABLE_GST_DEBUG
#define DEBUG_CAPS(capsaggreg, msg, caps) \
{ \
  gchar *_str = gst_caps_to_string(caps); \
  GST_DEBUG_OBJECT (capsaggreg, msg, _str); \
  g_free (_str); \
}
#else
#define DEBUG_CAPS(msg, caps) ((void) NULL)
#endif


GST_DEBUG_CATEGORY_STATIC (capsaggreg_debug);
#define GST_CAT_DEFAULT (capsaggreg_debug)


/* ElementFactory information. */
static GstElementDetails capsaggreg_details = {
  "Aggregate many inputs with capabilities negotiation",
  "Generic",
  "Move buffers from many potentially heterogeneous input pads "
      "to one output pad, negotiating capabilities on it as necessary.",
  "Martin Soto <martinsoto@users.sourceforge.net>"
};


/* CapsAggreg signals and args */
enum
{
  LAST_SIGNAL,
};

enum
{
  ARG_0,
  ARG_SINK_CNT,
};


static GstStaticPadTemplate capsaggreg_sink_template =
GST_STATIC_PAD_TEMPLATE ("sink%d",
    GST_PAD_SINK,
    GST_PAD_REQUEST,
    GST_STATIC_CAPS_ANY);

static GstStaticPadTemplate capsaggreg_src_template =
GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS_ANY);


static void capsaggreg_base_init (gpointer g_class);
static void capsaggreg_class_init (CapsAggregClass * klass);
static void capsaggreg_init (CapsAggreg * capsaggreg);
static void capsaggreg_finalize (GObject * object);

static void capsaggreg_set_property (GObject * object,
    guint prop_id, const GValue * value, GParamSpec * pspec);
static void capsaggreg_get_property (GObject * object,
    guint prop_id, GValue * value, GParamSpec * pspec);

static GstPad *capsaggreg_request_new_pad
    (GstElement * element, GstPadTemplate * templ, const gchar * unused);

static GstCaps *capsaggreg_sink_getcaps (GstPad * pad);

static gboolean capsaggreg_nego_src (CapsAggreg * capsaggreg,
    GstPad * new_active);
static gboolean capsaggreg_event (GstPad * pad, GstEvent * event);
static GstFlowReturn capsaggreg_chain (GstPad * pad, GstBuffer * buf);


static GstElementClass *parent_class = NULL;

//static guint capsaggreg_signals[LAST_SIGNAL] = { 0 };


GType
capsaggreg_get_type (void)
{
  static GType capsaggreg_type = 0;

  if (!capsaggreg_type) {
    static const GTypeInfo capsaggreg_info = {
      sizeof (CapsAggregClass),
      capsaggreg_base_init,
      NULL,
      (GClassInitFunc) capsaggreg_class_init,
      NULL,
      NULL,
      sizeof (CapsAggreg),
      0,
      (GInstanceInitFunc) capsaggreg_init,
    };
    capsaggreg_type = g_type_register_static (GST_TYPE_ELEMENT,
        "CapsAggreg", &capsaggreg_info, 0);
  }
  GST_DEBUG_CATEGORY_INIT (capsaggreg_debug, "capsaggreg", 0,
      "caps selector element");

  return capsaggreg_type;
}


static void
capsaggreg_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);

  gst_element_class_set_details (element_class, &capsaggreg_details);
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&capsaggreg_sink_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&capsaggreg_src_template));
}


static void
capsaggreg_class_init (CapsAggregClass * klass)
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass *) klass;
  gstelement_class = (GstElementClass *) klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  gobject_class->set_property = capsaggreg_set_property;
  gobject_class->get_property = capsaggreg_get_property;
  gobject_class->finalize = capsaggreg_finalize;

  g_object_class_install_property (gobject_class, ARG_SINK_CNT,
      g_param_spec_int ("sink-count", "sink-count",
          "Count of sink pads in this element",
          0, G_MAXINT, 0, G_PARAM_READABLE));

  gstelement_class->request_new_pad = capsaggreg_request_new_pad;
}


static void
capsaggreg_init (CapsAggreg * capsaggreg)
{
  capsaggreg->sinks = NULL;

  capsaggreg->src =
      gst_pad_new_from_template (gst_static_pad_template_get
      (&capsaggreg_src_template), "sink");
  gst_element_add_pad (GST_ELEMENT (capsaggreg), capsaggreg->src);

  /* No input pad to start with. */
  capsaggreg->cur_sink = NULL;

  capsaggreg->lock = g_mutex_new ();
  capsaggreg->no_current = g_cond_new ();
}


static void
capsaggreg_finalize (GObject * object)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (object);

  g_list_free (capsaggreg->sinks);
}


static void
capsaggreg_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec)
{
  CapsAggreg *capsaggreg;

  capsaggreg = CAPSAGGREG (object);

  switch (prop_id) {
    default:
      break;
  }
}


static void
capsaggreg_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec)
{
  CapsAggreg *capsaggreg;

  g_return_if_fail (GST_IS_CAPSAGGREG (object));

  capsaggreg = CAPSAGGREG (object);

  switch (prop_id) {
    case ARG_SINK_CNT:
      g_value_set_int (value, g_list_length (capsaggreg->sinks));
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static GstPad *
capsaggreg_request_new_pad (GstElement * element,
    GstPadTemplate * templ, const gchar * unused)
{
  CapsAggreg *capsaggreg;
  char *name;
  GstPad *sink;

  capsaggreg = CAPSAGGREG (element);

  /* Only sink pads can be requested. */
  if (templ->direction != GST_PAD_SINK) {
    GST_WARNING_OBJECT (capsaggreg, "non sink pad requested");
    return NULL;
  }

  name = g_strdup_printf ("sink%d", g_list_length (capsaggreg->sinks));
  sink = gst_pad_new_from_template (templ, name);
  g_free (name);

  gst_pad_set_getcaps_function (sink, capsaggreg_sink_getcaps);
  gst_pad_set_event_function (sink, capsaggreg_event);
  gst_pad_set_chain_function (sink, capsaggreg_chain);
  gst_element_add_pad (GST_ELEMENT (capsaggreg), sink);

  capsaggreg->sinks = g_list_append (capsaggreg->sinks, sink);

  return sink;
}


static GstCaps *
capsaggreg_sink_getcaps (GstPad * pad)
{
  //CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  return gst_pad_proxy_getcaps (pad);
}


static gboolean
capsaggreg_nego_src (CapsAggreg * capsaggreg, GstPad * new_active)
{
  gboolean res = TRUE;

  GST_CAPSAGGREG_LOCK (capsaggreg);

  if (capsaggreg->cur_sink == new_active) {
    goto done;
  }

  /* We have a new active sink. */

  /* Wait until the previous active sink (if any) receives its stop
     event. This is necessary to guarantee that no data is lost while
     switching. */
  while (capsaggreg->cur_sink != NULL) {
    g_cond_wait (capsaggreg->no_current, capsaggreg->lock);
  }

  capsaggreg->cur_sink = new_active;

  GST_DEBUG_OBJECT (capsaggreg, "new active source: '%s:%s'",
      GST_DEBUG_PAD_NAME (new_active));

 done:
  GST_CAPSAGGREG_UNLOCK (capsaggreg);
  return res;
}


static gboolean
capsaggreg_event (GstPad * pad, GstEvent * event)
{
  CapsAggreg *capsaggreg = CAPSAGGREG(gst_pad_get_parent (pad));
  gboolean res = TRUE;

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_CUSTOM_DOWNSTREAM:
    {
      const GstStructure *structure = gst_event_get_structure (event);

      if (gst_structure_has_name (structure, "application/x-gst-capspipe")) {
	const char *event_type =
	  gst_structure_get_string (structure, "event");

        if (strcmp (event_type, "start") == 0) {
          GST_DEBUG_OBJECT (capsaggreg,
              "start event received from pad '%s:%s'\n",
              GST_DEBUG_PAD_NAME (pad));
          capsaggreg_nego_src (capsaggreg, pad);
          gst_event_unref (event);
        } else if (strcmp (event_type, "stop") == 0) {
          GST_DEBUG_OBJECT (capsaggreg,
              "stop event received from pad '%s:%s'\n",
              GST_DEBUG_PAD_NAME (pad));

	  GST_CAPSAGGREG_LOCK (capsaggreg);
	  /* Clear the current sink, and awake any waiting threads. */
          capsaggreg->cur_sink = NULL;
	  g_cond_signal (capsaggreg->no_current);
	  GST_CAPSAGGREG_UNLOCK (capsaggreg);

          gst_event_unref (event);
        } else {
          g_return_val_if_reached (FALSE);
        }
      } else {
	GST_CAPSAGGREG_LOCK (capsaggreg);
        if (pad == capsaggreg->cur_sink) {
          res = gst_pad_push_event (capsaggreg->src, event);
        }
	GST_CAPSAGGREG_UNLOCK (capsaggreg);
      }
      break;
    }

    case GST_EVENT_EOS:
      res = gst_pad_event_default (pad, event);
      break;

    default:
      GST_CAPSAGGREG_LOCK (capsaggreg);
      if (pad == capsaggreg->cur_sink) {
        res = gst_pad_push_event (capsaggreg->src, event);
      }
      GST_CAPSAGGREG_UNLOCK (capsaggreg);
      break;
  }

  gst_object_unref (capsaggreg);
  return res;
}


static GstFlowReturn
capsaggreg_chain (GstPad * pad, GstBuffer * buf)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));
  GstFlowReturn res = GST_FLOW_OK;

  GST_CAPSAGGREG_LOCK (capsaggreg);

  if (capsaggreg->cur_sink == pad) {
    /* A buffer arrived on the active sink, forward it to the source
       pad. */
    res = gst_pad_push (capsaggreg->src, buf);
  } else {
    /* Buffers arriving when the pad hasn't been activated just get
       discarded. */
    GST_WARNING_OBJECT (capsaggreg, "dropping buffer %p", buf);
    gst_buffer_unref (buf);
  }

  GST_CAPSAGGREG_UNLOCK (capsaggreg);
  gst_object_unref (capsaggreg);
  return res;
}
