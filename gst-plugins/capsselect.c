/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * capsselect.c: Automatically select the output pad based on the
 *               capabilities of the input pad.
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
#include "capsselect.h"


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


GST_DEBUG_CATEGORY_STATIC (capsselect_debug);
#define GST_CAT_DEFAULT (capsselect_debug)


/* ElementFactory information. */
static GstElementDetails capsselect_details = {
  "Select one output based on capabilities",
  "Generic",
  "Automatically select the output pad based on the capabilities set for "
  "the input pad.",
  "Martin Soto <martinsoto@users.sourceforge.net>"
};


/* CapsSelect signals and args */
enum {
  LAST_SIGNAL,
};

enum {
  ARG_0,
  ARG_SOURCE_CNT,
};


static GstStaticPadTemplate capsselect_sink_template =
GST_STATIC_PAD_TEMPLATE (
  "sink",
  GST_PAD_SINK,
  GST_PAD_ALWAYS,
  GST_STATIC_CAPS_ANY
);

static GstStaticPadTemplate capsselect_src_template =
GST_STATIC_PAD_TEMPLATE (
  "src%d",
  GST_PAD_SRC,
  GST_PAD_REQUEST,
  GST_STATIC_CAPS_ANY
);


static void	capsselect_base_init	(gpointer g_class);
static void	capsselect_class_init   (CapsSelectClass *klass);
static void	capsselect_init		(CapsSelect *capsselect);
static void	capsselect_finalize	(GObject *object);

static void	capsselect_set_property	(GObject *object,
                                         guint prop_id, 
                                         const GValue *value,
                                         GParamSpec *pspec);
static void	capsselect_get_property	(GObject *object,
                                         guint prop_id, 
                                         GValue *value,
                                         GParamSpec *pspec);

static GstPad*	capsselect_request_new_pad
					(GstElement *element,
                                         GstPadTemplate *templ,
                                         const gchar *unused);

static void	capsselect_update_current
					(CapsSelect *capsselect);
static GstPadLinkReturn
		capsselect_sink_link	(GstPad *pad, const GstCaps *caps);
static void	capsselect_sink_unlink	(GstPad *pad);
static void	capsselect_src_linked	(GstPad *pad);
static void	capsselect_src_unlinked	(GstPad *pad);

static gboolean capsselect_handle_event (GstPad *pad, GstEvent *event);
static void	capsselect_chain	(GstPad *pad, GstData *data);


static GstElementClass *parent_class = NULL;
static guint capsselect_signals[LAST_SIGNAL] = { 0 };


GType
capsselect_get_type (void) 
{
  static GType capsselect_type = 0;

  if (!capsselect_type) {
    static const GTypeInfo capsselect_info = {
      sizeof (CapsSelectClass),
      capsselect_base_init,
      NULL,
      (GClassInitFunc)capsselect_class_init,
      NULL,
      NULL,
      sizeof (CapsSelect),
      0,
      (GInstanceInitFunc)capsselect_init,
    };
    capsselect_type = g_type_register_static (GST_TYPE_ELEMENT,
                                              "CapsSelect",
                                              &capsselect_info, 0);
  }
  GST_DEBUG_CATEGORY_INIT (capsselect_debug, "capsselect", 0,
                           "caps selector element");

  return capsselect_type;
}


static void
capsselect_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &capsselect_details);
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&capsselect_sink_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&capsselect_src_template));
}


static void
capsselect_class_init (CapsSelectClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass*)klass;
  gstelement_class = (GstElementClass*)klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  g_object_class_install_property (gobject_class, ARG_SOURCE_CNT,
    g_param_spec_int ("source-count", "source-count",
                      "Count of source pads in this element",
                      0, G_MAXINT, 0, G_PARAM_READABLE));

  gobject_class->set_property = capsselect_set_property;
  gobject_class->get_property = capsselect_get_property;
  gobject_class->finalize = capsselect_finalize;

  gstelement_class->request_new_pad = capsselect_request_new_pad;
}


static void 
capsselect_init (CapsSelect *capsselect) 
{
  capsselect->sink = gst_pad_new_from_template (
                     gst_static_pad_template_get (&capsselect_sink_template),
                     "sink");
  gst_element_add_pad (GST_ELEMENT (capsselect), capsselect->sink);
  gst_pad_set_link_function (capsselect->sink, capsselect_sink_link);
  gst_pad_set_unlink_function (capsselect->sink, capsselect_sink_unlink);
  gst_pad_set_chain_function (capsselect->sink, capsselect_chain);

  capsselect->srcs = g_array_new (FALSE, FALSE, sizeof(GstPad *));

  /* No output pad to start with. */
  capsselect->cur_src = NULL;
  capsselect->cur_caps = NULL;
}


static void
capsselect_finalize (GObject *object)
{
  CapsSelect *capsselect = CAPSSELECT (object);

  g_array_free (capsselect->srcs, TRUE);
}


static void
capsselect_set_property (GObject *object, guint prop_id,
                         const GValue *value, GParamSpec *pspec)
{
  CapsSelect *capsselect;

  capsselect = CAPSSELECT (object);

  switch (prop_id) {
    default:
      break;
  }
}


static void   
capsselect_get_property (GObject *object, guint prop_id,
                         GValue *value, GParamSpec *pspec)
{
  CapsSelect *capsselect;
 
  g_return_if_fail (GST_IS_CAPSSELECT (object));
 
  capsselect = CAPSSELECT (object);
  
  switch (prop_id) {
  case ARG_SOURCE_CNT:
    g_value_set_int (value, capsselect->srcs->len);
    break;
  default:
    G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    break;
  }
}


static GstPad*
capsselect_request_new_pad (GstElement *element,
                            GstPadTemplate *templ,
                            const gchar *unused) 
{
  CapsSelect *capsselect;
  char *name;
  GstPad *src;
  
  /* Only source pads can be requested. */
  if (templ->direction != GST_PAD_SRC) {
    GST_WARNING ("non source pad requested");
    return NULL;
  }
  
  capsselect = CAPSSELECT (element);
  
  name = g_strdup_printf ("src%d", capsselect->srcs->len);
  src = gst_pad_new_from_template (templ, name);
  g_free (name);
  
  g_signal_connect (src, "linked",
                    G_CALLBACK (capsselect_src_linked), NULL);
  g_signal_connect (src, "unlinked",
                    G_CALLBACK (capsselect_src_unlinked), NULL);
  gst_element_add_pad (GST_ELEMENT (capsselect), src);
  
  g_array_append_val (capsselect->srcs, src);
  
  return src;
}


static void
capsselect_update_current (CapsSelect *capsselect)
{
  int i;
  GstPad *src;
  GstPadLinkReturn ret;

  capsselect->cur_src = NULL;

  if (capsselect->cur_caps == NULL) {
    return;
  }

  i = 0;
  while (i < capsselect->srcs->len) {
    src = g_array_index(capsselect->srcs, GstPad *, i);

    ret = gst_pad_try_set_caps (src, capsselect->cur_caps);
    if (GST_PAD_LINK_SUCCESSFUL (ret)) {
      capsselect->cur_src = src;
      GST_DEBUG ("Setting current source to '%s'", GST_PAD_NAME(src));
      return;
    }

    i++;
  }

  GST_DEBUG ("No suitable source pad found");
}


static GstPadLinkReturn
capsselect_sink_link (GstPad *pad, const GstCaps *caps)
{
  CapsSelect *capsselect = CAPSSELECT (gst_pad_get_parent (pad));

  DEBUG_CAPS ("linking sink pad with caps: %s", caps);

  /* Store this caps. */
  gst_caps_replace (&capsselect->cur_caps, gst_caps_copy (caps));

  capsselect_update_current (capsselect);

  /* We allow linking regardless of the caps. */
  return GST_PAD_LINK_OK;
}


static void
capsselect_sink_unlink (GstPad *pad)
{
  CapsSelect *capsselect = CAPSSELECT (gst_pad_get_parent (pad));

  GST_DEBUG ("unlinking sink pad");

  capsselect->cur_src = NULL;
  if (capsselect->cur_caps != NULL) {
    gst_caps_free (capsselect->cur_caps);
  }
  capsselect->cur_caps = NULL;
}


static void
capsselect_src_linked (GstPad *pad)
{
  CapsSelect *capsselect = CAPSSELECT (gst_pad_get_parent (pad));

  GST_DEBUG ("linking pad '%s'", GST_PAD_NAME(pad));
  capsselect_update_current (capsselect);
}


static void
capsselect_src_unlinked (GstPad *pad)
{
  CapsSelect *capsselect = CAPSSELECT (gst_pad_get_parent (pad));

  GST_DEBUG ("unlinking pad '%s'", GST_PAD_NAME(pad));
  capsselect_update_current (capsselect);
}


static gboolean
capsselect_handle_event (GstPad *pad, GstEvent *event)
{
  GstEventType type;
  CapsSelect *capsselect = CAPSSELECT (gst_pad_get_parent (pad));

  type = event ? GST_EVENT_TYPE (event) : GST_EVENT_UNKNOWN;

  switch (type) {
  default:
    gst_pad_event_default (pad, event);
    break;
  }

  return TRUE;
}


static void 
capsselect_chain (GstPad *pad, GstData *data)
{
  GstBuffer *buf = GST_BUFFER (data);
  CapsSelect *capsselect;

  g_return_if_fail (pad != NULL);
  g_return_if_fail (GST_IS_PAD (pad));
  g_return_if_fail (buf != NULL);

  capsselect = CAPSSELECT (gst_pad_get_parent (pad));

  if (GST_IS_EVENT (buf)) {
    capsselect_handle_event (pad, GST_EVENT (buf));
    return;
  }

  if (capsselect->cur_src == NULL) {
    /* No current source pad, discard the buffer. */
    GST_LOG ("dropping buffer");
    gst_buffer_unref (buf);
  }
  else {
    gst_pad_push (capsselect->cur_src, data);
  }
}


/*
 * Plugin Initialization
 */

static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "capsselect", GST_RANK_NONE,
                             GST_TYPE_CAPSSELECT)) {
    return FALSE;
  }

  return TRUE;
}


GST_PLUGIN_DEFINE (
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "capsselect",
  "Select output pad based on capabilities.",
  plugin_init,
  VERSION,
  "LGPL",
  GST_PACKAGE,
  GST_ORIGIN
)
