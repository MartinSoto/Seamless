/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * capsaggreg.c: Aggregate contents from multiple sink pads into a 
 *               single source negociating capabilities as needed.
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
#define DEBUG_CAPS(msg, caps) \
{ \
  gchar *_str = gst_caps_to_string(caps); \
  GST_DEBUG (msg, _str); \
  g_free (_str); \
}
#else
#define DEBUG_CAPS(msg, caps) ((void) NULL)
#endif


GST_DEBUG_CATEGORY_STATIC (capsaggreg_debug);
#define GST_CAT_DEFAULT (capsaggreg_debug)


/* ElementFactory information. */
static GstElementDetails capsaggreg_details = {
  "Aggregate many inputs with capabilities negociation",
  "Generic",
  "Move buffers from many potentially heterogeneous input pads "
  "to one output pad, negociating capabilities on it as necessary.",
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

static gboolean capsaggreg_handle_event (GstPad *pad, GstEvent *event);
static void	capsaggreg_chain	(GstPad *pad, GstData *data);


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
  capsaggreg->sinks = g_array_new (FALSE, FALSE, sizeof(GstPad *));

  capsaggreg->src = gst_pad_new_from_template (
                     gst_static_pad_template_get (&capsaggreg_src_template),
                     "sink");
  g_signal_connect (capsaggreg->src, "linked",
                    G_CALLBACK (capsaggreg_src_linked), NULL);
  gst_element_add_pad (GST_ELEMENT (capsaggreg), capsaggreg->src);

  /* No input pad to start with. */
  capsaggreg->cur_sink = NULL;
}


static void
capsaggreg_finalize (GObject *object)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (object);

  g_array_free (capsaggreg->sinks, TRUE);
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
    g_value_set_int (value, capsaggreg->sinks->len);
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
  
  /* Only sink pads can be requested. */
  if (templ->direction != GST_PAD_SINK) {
    GST_WARNING ("non sink pad requested");
    return NULL;
  }
  
  capsaggreg = CAPSAGGREG (element);
  
  name = g_strdup_printf ("sink%d", capsaggreg->sinks->len);
  sink = gst_pad_new_from_template (templ, name);
  g_free (name);
  gst_pad_set_link_function (sink, capsaggreg_sink_link);
  gst_pad_set_getcaps_function (sink, capsaggreg_sink_getcaps);
  gst_pad_set_chain_function (sink, capsaggreg_chain);
  gst_element_add_pad (GST_ELEMENT (capsaggreg), sink);
  
  g_array_append_val (capsaggreg->sinks, sink);
  
  return sink;
}


static GstCaps *
capsaggreg_sink_getcaps (GstPad *pad)
{
  CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  return gst_pad_get_allowed_caps (capsaggreg->src);
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
  int i;
  GstPad *sink;
  GstPadLinkReturn ret;

  i = 0;
  while (i < capsaggreg->sinks->len) {
    sink = g_array_index(capsaggreg->sinks, GstPad *, i);

    ret = gst_pad_renegotiate (sink);
    if (GST_PAD_LINK_FAILED (ret)) {
      GST_WARNING ("negotiation failed for pad '%s'", GST_PAD_NAME(sink));
    }

    i++;
  }
}


static gboolean
capsaggreg_handle_event (GstPad *pad, GstEvent *event)
{
  GstEventType type;
  CapsAggreg *capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  type = event ? GST_EVENT_TYPE (event) : GST_EVENT_UNKNOWN;

  switch (type) {
  default:
    gst_pad_event_default (pad, event);
    break;
  }

  return TRUE;
}


static void 
capsaggreg_chain (GstPad *pad, GstData *data)
{
  GstBuffer *buf = GST_BUFFER (data);
  CapsAggreg *capsaggreg;
  const GstCaps *caps;
  GstPadLinkReturn ret;

  g_return_if_fail (pad != NULL);
  g_return_if_fail (GST_IS_PAD (pad));
  g_return_if_fail (buf != NULL);

  capsaggreg = CAPSAGGREG (gst_pad_get_parent (pad));

  if (GST_IS_EVENT (buf)) {
    capsaggreg_handle_event (pad, GST_EVENT (buf));
    return;
  }

  if (capsaggreg->cur_sink != pad) {
    /* We have a new active sink. Try to negociate caps for it. */
    caps = gst_pad_get_negotiated_caps (pad);
    if (caps == NULL) {
      GST_WARNING ("unable to negotiate caps for pad '%s'",
                   GST_PAD_NAME(pad));
      gst_buffer_unref (buf);
      return;
    }

    ret = gst_pad_try_set_caps (capsaggreg->src, caps);
    if (GST_PAD_LINK_FAILED (ret)) {
      GST_WARNING ("unable to negotiate caps for pad '%s'",
                   GST_PAD_NAME(pad));
      gst_buffer_unref (buf);
      return;
    }

    DEBUG_CAPS ("new caps set: %s", caps);

    capsaggreg->cur_sink = pad;
    GST_LOG ("new active source: '%s'", GST_PAD_NAME(pad));
  }

  gst_pad_push (capsaggreg->src, data);
}


/*
 * Plugin Initialization
 */

static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "capsaggreg", GST_RANK_NONE,
                             GST_TYPE_CAPSAGGREG)) {
    return FALSE;
  }

  return TRUE;
}


GST_PLUGIN_DEFINE (
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "capsaggreg",
  "Aggregate many inputs with capabilities negotiation.",
  plugin_init,
  VERSION,
  "LGPL",
  GST_PACKAGE,
  GST_ORIGIN
)
