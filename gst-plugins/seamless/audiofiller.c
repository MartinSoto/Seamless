/* Seamless DVD Player
 * Copyright (C) 2004-2006 Martin Soto <martinsoto@users.sourceforge.net>
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

#include "audiofiller.h"


#ifndef __GST_DISABLE_GST_DEBUG
#define LOG_CAPS(obj, msg, caps) \
{ \
  gchar *_str = gst_caps_to_string(caps); \
  GST_LOG_OBJECT (obj, msg, _str); \
  g_free (_str); \
}
#else
#define LOG_CAPS(obj, msg, caps) ((void) NULL)
#endif


/* Samples per second. */
#define SAMPLES_PER_SECOND 48000

/* Sample size: 16 bits * 2 channels = 4 bytes. */
#define SAMPLE_SIZE 4

/* Maximal silence packet size in samples: 4800 = 0.1s. */
#define MAX_PACKET_SIZE 4800


GST_DEBUG_CATEGORY_STATIC (audiofiller_debug);
#define GST_CAT_DEFAULT (audiofiller_debug)


/* ElementFactory information. */
static GstElementDetails audiofiller_details = GST_ELEMENT_DETAILS (
  "DVD audio gap filler",
  "",
  "Fills audio gaps based on DVD events",
  "Martin Soto <martinsoto@users.sourceforge.net>");


/* AudioFiller signals and properties. */
enum {
  LAST_SIGNAL,
};

enum {
  PROP_0,
};


static GstStaticPadTemplate audiofiller_sink_template =
    GST_STATIC_PAD_TEMPLATE ("sink",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS_ANY);

static GstStaticPadTemplate audiofiller_src_template =
    GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS_ANY);


static GstStaticCaps silence_caps =
GST_STATIC_CAPS("audio/x-lpcm,"
    "width=(int)16,"
    "rate=(int)48000,"
    "channels=(int)2,"
    "dynamic_range=(int)128,"
    "emphasis=(boolean)false,"
    "mute=(boolean)false");


#define _do_init(bla) \
    GST_DEBUG_CATEGORY_INIT (audiofiller_debug, "audiofiller", 0, \
        "DVD audio gap filler element");

GST_BOILERPLATE_FULL (AudioFiller, audiofiller, GstBaseTransform,
    GST_TYPE_BASE_TRANSFORM, _do_init);

static void
audiofiller_base_init(gpointer g_class);
static void
audiofiller_class_init (AudioFillerClass *klass);
static void 
audiofiller_init (AudioFiller * audiofiller, AudioFillerClass * klass);

static void
audiofiller_set_property (GObject *object, guint prop_id, const GValue *value,
    GParamSpec *pspec);
static void
audiofiller_get_property (GObject *object, guint prop_id, GValue *value,
    GParamSpec *pspec);

static gboolean
audiofiller_event (GstBaseTransform *trans, GstEvent *event);
static gboolean
audiofiller_push_silence (AudioFiller * audiofiller, GstClockTime start,
    GstClockTime stop);

static GstFlowReturn
audiofiller_transform_ip (GstBaseTransform *trans, GstBuffer *buf);


/* static guint audiofiller_signals[LAST_SIGNAL] = { 0 }; */


static void
audiofiller_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &audiofiller_details);
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&audiofiller_src_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&audiofiller_sink_template));
}


static void
audiofiller_class_init (AudioFillerClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;
  GstBaseTransformClass *gstbase_transform_class;

  gobject_class = G_OBJECT_CLASS (klass);
  gstelement_class = GST_ELEMENT_CLASS (klass);
  gstbase_transform_class = (GstBaseTransformClass *) klass;

  parent_class = g_type_class_ref (GST_TYPE_BASE_TRANSFORM);

  gobject_class->set_property = audiofiller_set_property;
  gobject_class->get_property = audiofiller_get_property;

  gstbase_transform_class->event = audiofiller_event;
  gstbase_transform_class->transform_ip = audiofiller_transform_ip;
}


static void 
audiofiller_init (AudioFiller * audiofiller, AudioFillerClass * klass)
{
}


static void
audiofiller_set_property (GObject *object, guint prop_id,
    const GValue *value, GParamSpec *pspec)
{
  /* AudioFiller *audiofiller = AUDIOFILLER (object); */

  g_return_if_fail (GST_IS_AUDIOFILLER (object));
 
  switch (prop_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static void   
audiofiller_get_property (GObject *object, guint prop_id,
    GValue *value, GParamSpec *pspec)
{
  AudioFiller *audiofiller;
 
  g_return_if_fail (GST_IS_AUDIOFILLER (object));
 
  audiofiller = AUDIOFILLER (object);
  
  switch (prop_id) {
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static gboolean
audiofiller_event (GstBaseTransform *trans, GstEvent *event)
{
  gboolean result = TRUE;
  AudioFiller *audiofiller = AUDIOFILLER (trans);

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_CUSTOM_DOWNSTREAM:
    {
      const GstStructure *structure = gst_event_get_structure (event);
      const char *event_type;

      if (!gst_structure_has_name (structure, "application/x-gst-dvd")) {
	break;
      }

      event_type = gst_structure_get_string (structure, "event");

      if (strcmp (event_type, "dvd-audio-fill-gap") == 0) {
	GstClockTime start, stop;

	if (!gst_structure_get_clock_time (structure, "start",
		&start) ||
	    !gst_structure_get_clock_time (structure, "stop",
		&stop)) {
	  GST_WARNING_OBJECT (audiofiller,
	      "incorrect dvd-audio-fill-gap event");
	  result = FALSE;
	  goto done;
	}

	GST_DEBUG_OBJECT (audiofiller,
	    "audio-fill-gap event received, start: %0.3fs, "
	    "stop: %0.3fs", (1.0 * start) / GST_SECOND,
	    (1.0 * stop) / GST_SECOND);

	result = audiofiller_push_silence (audiofiller, start, stop);
      }

      break;
    }

    default:
      break;
  }

 done:
  return result;
}


static gboolean
audiofiller_push_silence (AudioFiller * audiofiller, GstClockTime start,
    GstClockTime stop)
{
  gboolean result = TRUE;
  guint samples, buf_samples;
  guint size;
  GstBuffer *buf;
  GstCaps *caps;

  /* Total samples to send. */
  samples = (SAMPLES_PER_SECOND * (stop - start)) / GST_SECOND;

  while (samples > 0) {
    if (samples >= MAX_PACKET_SIZE) {
      buf_samples = MAX_PACKET_SIZE;
    } else {
      buf_samples = samples;
    }
    size = buf_samples * SAMPLE_SIZE;
    samples -= buf_samples;

    buf = gst_buffer_new_and_alloc (size);

    caps = gst_static_caps_get (&silence_caps);
    gst_buffer_set_caps (buf, caps);
    gst_caps_unref (caps);

    /* Set the contents to zero. */
    memset (GST_BUFFER_DATA (buf), 0, size);

    GST_BUFFER_TIMESTAMP (buf) = start;
    start += (buf_samples * GST_SECOND) / SAMPLES_PER_SECOND;

    if (gst_pad_push (GST_BASE_TRANSFORM (audiofiller)->srcpad, buf) !=
	GST_FLOW_OK) {
      result = FALSE;
      goto done;
    }

    GST_LOG_OBJECT (audiofiller,
	"Sent filler buffer, timestamp %0.3fs, size: %d",
	(1.0 * GST_BUFFER_TIMESTAMP (buf)) / GST_SECOND,
	GST_BUFFER_SIZE (buf));
  }
  
 done:
  return result;
}


static GstFlowReturn
audiofiller_transform_ip (GstBaseTransform *trans, GstBuffer *buf)
{
  GST_LOG_OBJECT (trans, "Forwarded buffer, timestamp %0.3fs",
      (1.0 * GST_BUFFER_TIMESTAMP (buf)) / GST_SECOND);
  return GST_FLOW_OK;
}
