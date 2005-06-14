/* GStreamer
 * Copyright (C) 2004-2005 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * capsaggreg.c: Aggregate contents from multiple sink pads into a 
 *               single source negotiating capabilities as needed.
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
enum {
  LAST_SIGNAL,
};

enum {
  ARG_0,
  ARG_SINK_CNT,
};


static GstStaticPadTemplate capsaggreg_sink_template =
GST_STATIC_PAD_TEMPLATE (
  "sink%d",
  GST_PAD_SINK,
  GST_PAD_REQUEST,
  GST_STATIC_CAPS_ANY
);

static GstStaticPadTemplate capsaggreg_src_template =
GST_STATIC_PAD_TEMPLATE (
  "src",
  GST_PAD_SRC,
  GST_PAD_ALWAYS,
  GST_STATIC_CAPS_ANY
);


static void	capsaggreg_base_init	(gpointer g_class);
static void	capsaggreg_class_init   (CapsAggregClass *klass);
static void	capsaggreg_init		(CapsAggreg *capsaggreg);
static void	capsaggreg_finalize	(GObject *object);

static void	capsaggreg_set_property	(GObject *object,
                                         guint prop_id, 
                                         const GValue *value,
                                         GParamSpec *pspec);
static void	capsaggreg_get_property	(GObject *object,
                                         guint prop_id, 
                                         GValue *value,
                                         GParamSpec *pspec);

static GstPad*	capsaggreg_request_new_pad
					(GstElement *element,
                                         GstPadTemplate *templ,
                                         const gchar *unused);

static GstPadLinkReturn
		capsaggreg_sink_link	(GstPad *pad,
                                         const GstCaps *caps);
static GstCaps* capsaggreg_sink_getcaps	(GstPad *pad);
static void	capsaggreg_src_linked	(GstPad *pad);

static void	capsaggreg_nego_src	(CapsAggreg * capsaggreg, GstPad *pad);
static void	capsaggreg_handle_event (CapsAggreg * capsaggreg, GstPad *pad,
					 GstEvent * event);
static void	capsaggreg_loop		(GstElement * element);


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
      (GClassInitFunc)capsaggreg_class_init,
      NULL,
      NULL,
      sizeof (CapsAggreg),
      0,
      (GInstanceInitFunc)capsaggreg_init,
    };
    capsaggreg_type = g_type_register_static (GST_TYPE_ELEMENT,
                                              "CapsAggreg",
                                              &capsaggreg_info, 0);
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
capsaggreg_class_init (CapsAggregClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass*)klass;
  gstelement_class = (GstElementClass*)klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  g_object_class_install_property (gobject_class, ARG_SINK_CNT,
    g_param_spec_int ("sink-count", "sink-count",
                      "Count of sink pads in this element",
                      0, G_MAXINT, 0, G_PARAM_READABLE));

  gobject_class->set_property = capsaggreg_set_property;
  gobject_class->get_property = capsaggreg_get_property;
  gobject_class->finalize = capsaggreg_finalize;

  gstelement_class->request_new_pad = capsaggreg_request_new_pad;
}


static void 
capsaggreg_init (CapsAggreg *capsaggreg) 
{
  GST_FLAG_SET (capsaggreg, GST_ELEMENT_EVENT_AWARE);

  capsaggreg->sinks = NULL;

  capsaggreg->src = gst_pad_new_from_template (
                     gst_static_pad_template_get (&capsaggreg_src_template),
                     "sink");
  g_signal_connect (capsaggreg->src, "linked",
                    G_CALLBACK (capsaggreg_src_linked), NULL);
  gst_element_add_pad (GST_ELEMENT (capsaggreg), capsaggreg->src);

  gst_element_set_loop_function (GST_ELEMENT (capsaggreg), capsaggreg_loop);

  /* No input pad to start with. */
  capsaggreg->cur_sink = NULL;
}


static void
capsaggreg_finalize (GObject *object)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (object);

  g_list_free (capsaggreg->sinks);
}


static void
capsaggreg_set_property (GObject *object, guint prop_id,
                         const GValue *value, GParamSpec *pspec)
{
  CapsAggreg *capsaggreg;

  capsaggreg = CAPSAGGREG (object);

  switch (prop_id) {
    default:
      break;
  }
}


static void   
capsaggreg_get_property (GObject *object, guint prop_id,
                         GValue *value, GParamSpec *pspec)
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


static GstPad*
capsaggreg_request_new_pad (GstElement *element,
                            GstPadTemplate *templ,
                            const gchar *unused) 
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
  gst_pad_set_link_function (sink, capsaggreg_sink_link);
  gst_pad_set_getcaps_function (sink, capsaggreg_sink_getcaps);
  gst_element_add_pad (GST_ELEMENT (capsaggreg), sink);
  
  capsaggreg->sinks = g_list_append (capsaggreg->sinks, sink);
  
  return sink;
}


static GstCaps *
capsaggreg_sink_getcaps (GstPad *pad)
{
  //CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  return gst_pad_proxy_getcaps (pad);
}


static GstPadLinkReturn
capsaggreg_sink_link (GstPad *pad, const GstCaps *caps)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  if (pad != capsaggreg->cur_sink) {
    return GST_PAD_LINK_OK;
  }
   
  return gst_pad_try_set_caps (capsaggreg->src, caps);
}


static void
capsaggreg_src_linked (GstPad *pad)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  GList *ptr;
  GstPad *sink;
  GstPadLinkReturn ret;

  for (ptr = capsaggreg->sinks; ptr != NULL; ptr = ptr->next) {
    sink = ptr->data;

    ret = gst_pad_renegotiate (sink);
    if (GST_PAD_LINK_FAILED (ret)) {
      GST_WARNING_OBJECT (capsaggreg, "negotiation failed for pad '%s'",
			  GST_PAD_NAME(sink));
    }
  }
}


static void
capsaggreg_nego_src (CapsAggreg * capsaggreg, GstPad * pad)
{
  const GstCaps *caps;
  GstPadLinkReturn ret;

  /* We have a new active sink. Try to (re)negotiate the source caps. */

  capsaggreg->cur_sink = NULL;

  caps = gst_pad_get_negotiated_caps (pad);
  if (caps == NULL) {
    GST_WARNING_OBJECT (capsaggreg,
			"unable to get caps from pad '%s:%s'",
			GST_DEBUG_PAD_NAME(pad));
    return;
  }

  ret = gst_pad_try_set_caps (capsaggreg->src, caps);
  if (GST_PAD_LINK_FAILED (ret)) {
    GST_WARNING_OBJECT (capsaggreg,
			"unable to negotiate caps for pad '%s:%s'",
			GST_DEBUG_PAD_NAME(capsaggreg->src));
    return;
  }

  DEBUG_CAPS (capsaggreg, "new caps set: %s", caps);

  capsaggreg->cur_sink = pad;

  GST_DEBUG_OBJECT (capsaggreg, "new active source: '%s:%s'",
		    GST_DEBUG_PAD_NAME(pad));
}


static void
capsaggreg_handle_event (CapsAggreg * capsaggreg, GstPad *pad,
			 GstEvent * event)
{
  switch (GST_EVENT_TYPE (event)) {
  case GST_EVENT_ANY:
    {
      GstStructure *structure = event->event_data.structure.structure;
      const char *event_type = gst_structure_get_string (structure, "event");

      if (strcmp (gst_structure_get_name (structure),
		  "application/x-gst-capspipe") == 0) {
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
	  capsaggreg->cur_sink = NULL;
	  gst_event_unref (event);
	} else {
	  g_return_if_reached ();
	}
      }
      else {
	if (capsaggreg->cur_sink != NULL) {
	  gst_pad_push (capsaggreg->src, GST_DATA (event));
	}
      }
    }
    break;

  case GST_EVENT_EOS:
    gst_pad_event_default (pad, event);
    break;

  default:
    if (capsaggreg->cur_sink != NULL) {
      gst_pad_push (capsaggreg->src, GST_DATA (event));
    }
    break;
  }
}


static void
capsaggreg_loop (GstElement * element)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (element);

  GstData *data;
  GstPad *read_from;

  if (capsaggreg->cur_sink == NULL) {
    /* We are waiting for a start event. It may come from any sink. */
    data = gst_pad_collectv (&read_from, capsaggreg->sinks);

    if (GST_IS_EVENT (data)) {
      capsaggreg_handle_event (capsaggreg, read_from, GST_EVENT (data));
    } else {
      /* Retry negotiation. */
      capsaggreg_nego_src (capsaggreg, read_from);
      if (capsaggreg->cur_sink == NULL) {
	GST_WARNING_OBJECT (capsaggreg, "dropping data %p", data);
      } else {
	gst_pad_push (capsaggreg->src, data);
      }
    }
  } else {
    data = gst_pad_pull (capsaggreg->cur_sink);

    if (GST_IS_EVENT (data)) {
      capsaggreg_handle_event (capsaggreg, capsaggreg->cur_sink,
			       GST_EVENT (data));
    } else {
      gst_pad_push (capsaggreg->src, data);
    }
  }
}

