/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
 * Portions copyright Jaroslav Kysela <perex@suse.cz>
 *
 * alsaspdifsink.c: Audio sink for SP/DIF interfaces trough ALSA
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

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <errno.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>

#include <gst/gst.h>
#include <gst/gstclock.h>
#include <gst/audio/audioclock.h>

#include "alsaspdifsink.h"


GST_DEBUG_CATEGORY_STATIC (alsaspdifsink_debug);
#define GST_CAT_DEFAULT (alsaspdifsink_debug)


/* The size in bytes of an IEC958 frame. */
#define IEC958_FRAME_SIZE 6144

/* The duration of a single IEC958 frame. */
#define IEC958_FRAME_DURATION (32 * GST_MSECOND)

/* Maximal synchronization difference.  Measures will be taken if
   block timestamps differ from actual playing time in more than this
   value. */
#define MAX_SYNC_DIFF (IEC958_FRAME_DURATION * 0.7)


/* Size in bytes of an ALSA PCM frame. */
#define ALSASPDIFSINK_BYTES_PER_FRAME(sink) \
  (((sink)->out_config.bits / 8) * (sink)->out_config.channels)

/* Playing time for the given number of ALSA PCM frames. */
#define ALSASPDIFSINK_TIME_PER_FRAMES(sink, frames) \
  (((GstClockTime) (frames) * GST_SECOND) / (sink)->out_config.rate)

/* Number of ALSA PCM frames for the given playing time. */
#define ALSASPDIFSINK_FRAMES_PER_TIME(sink, time) \
  (((GstClockTime) (sink)->out_config.rate * (time)) / GST_SECOND)


/* ElementFactory information. */
static GstElementDetails alsaspdifsink_details = {
  "SP/DIF ALSA audiosink",
  "audio/x-iec958",
  "Feeds audio to SP/DIF interfaces through the ALSA sound driver",
  "Martin Soto <martinsoto@users.sourceforge.net>"
};


/* AlsaSPDIFSink signals and args */
/*enum {
  LAST_SIGNAL
};*/

enum {
  ARG_0,
};

static GstStaticPadTemplate alsaspdifsink_sink_factory =
GST_STATIC_PAD_TEMPLATE (
  "sink",
  GST_PAD_SINK,
  GST_PAD_ALWAYS,
  GST_STATIC_CAPS (
    "audio/x-raw-int, "
      "law = (int) 0, "
      "endianness = (int) " G_STRINGIFY (G_BYTE_ORDER) ", "
      "signed = (boolean) true, "
      "width = (int) 16, "
      "depth = (int) 16, "
      "rate = (int) 48000, "
      "channels = (int) 2;"
    "audio/x-iec958"
  )
);


static void	alsaspdifsink_base_init		(gpointer g_class);
static void	alsaspdifsink_class_init   	(AlsaSPDIFSinkClass *klass);
static void	alsaspdifsink_init		(AlsaSPDIFSink *sink);

static void	alsaspdifsink_set_property	(GObject *object,
                                                 guint prop_id, 
                                                 const GValue *value,
                                                 GParamSpec *pspec);
static void	alsaspdifsink_get_property	(GObject *object,
                                                 guint prop_id, 
						 GValue *value,
                                                 GParamSpec *pspec);

static GstPadLinkReturn
		alsaspdifsink_link		(GstPad *pad,
                                                 const GstCaps *caps);

static gboolean alsaspdifsink_open	 	(AlsaSPDIFSink *sink);
static int	alsaspdifsink_alsa_open		(AlsaSPDIFSink *sink);
static void 	alsaspdifsink_close 		(AlsaSPDIFSink *sink);

static void	alsaspdifsink_write_samples	(AlsaSPDIFSink *sink,
                                                 gint16 *output_samples,
                                                 guint num_frames);

static GstClockTime
		alsaspdifsink_get_time		(GstClock *clock,
                                                 gpointer data);
static GstClock 
	       *alsaspdifsink_get_clock		(GstElement *element);
static void	alsaspdifsink_set_clock		(GstElement *element,
                                                 GstClock *clock);

static GstClockTime
		alsaspdifsink_current_delay	(AlsaSPDIFSink *sink);

static gboolean alsaspdifsink_handle_event      (GstPad *pad,
                                                 GstEvent *event);
static void	alsaspdifsink_chain		(GstPad *pad, GstData *_data);

static GstElementStateReturn
		alsaspdifsink_change_state	(GstElement *element);

static void	alsaspdifsink_flush		(AlsaSPDIFSink *sink);


static GstElementClass *parent_class = NULL;
/*static guint alsaspdifsink_signals[LAST_SIGNAL] = { 0 };*/


extern GType
alsaspdifsink_get_type (void) 
{
  static GType alsaspdifsink_type = 0;

  if (!alsaspdifsink_type) {
    static const GTypeInfo alsaspdifsink_info = {
      sizeof(AlsaSPDIFSinkClass),
      alsaspdifsink_base_init,
      NULL,
      (GClassInitFunc) alsaspdifsink_class_init,
      NULL,
      NULL,
      sizeof (AlsaSPDIFSink),
      0,
      (GInstanceInitFunc) alsaspdifsink_init,
    };
    alsaspdifsink_type = g_type_register_static (GST_TYPE_ELEMENT,
                                                 "AlsaSPDIFSink",
                                                 &alsaspdifsink_info, 0);

    GST_DEBUG_CATEGORY_INIT (alsaspdifsink_debug, "alsaspdifsink", 0,
                             "DXR3 audio sink element");
  }

  return alsaspdifsink_type;
}


static void
alsaspdifsink_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &alsaspdifsink_details);
  gst_element_class_add_pad_template (element_class,
	gst_static_pad_template_get (&alsaspdifsink_sink_factory));
  gst_element_class_set_details (element_class,
				 &alsaspdifsink_details);
}


static void
alsaspdifsink_class_init (AlsaSPDIFSinkClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass*)klass;
  gstelement_class = (GstElementClass*)klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  gobject_class->set_property = alsaspdifsink_set_property;
  gobject_class->get_property = alsaspdifsink_get_property;

  gstelement_class->change_state = alsaspdifsink_change_state;
  gstelement_class->set_clock = alsaspdifsink_set_clock;
  gstelement_class->get_clock = alsaspdifsink_get_clock;
}


static void 
alsaspdifsink_init (AlsaSPDIFSink *sink) 
{
  GstPadTemplate *temp;

  /* Create the sink pad. */
  temp = gst_static_pad_template_get (&alsaspdifsink_sink_factory);
  sink->sinkpad = gst_pad_new_from_template (temp, "sink");
  gst_pad_set_chain_function (sink->sinkpad, alsaspdifsink_chain);
  gst_pad_set_link_function (sink->sinkpad, alsaspdifsink_link);
  gst_element_add_pad (GST_ELEMENT (sink), sink->sinkpad);

  GST_FLAG_SET (GST_ELEMENT (sink), GST_ELEMENT_EVENT_AWARE);

  sink->passtrough = FALSE;

  sink->cur_ts = 0;

  /* Create the provided clock. */
  sink->provided_clock = gst_audio_clock_new ("audioclock",
                                              alsaspdifsink_get_time,
                                              sink);
  gst_object_set_parent (GST_OBJECT (sink->provided_clock),
                         GST_OBJECT (sink));
  sink->clock_time = 0;
}


static void
alsaspdifsink_set_property (GObject *object, guint prop_id,
                           const GValue *value, GParamSpec *pspec)
{
  AlsaSPDIFSink *sink;

  sink = ALSASPDIFSINK (object);
  
  switch (prop_id) {
  default:
    G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    break;
  }
}


static void   
alsaspdifsink_get_property (GObject *object, guint prop_id,
                            GValue *value, GParamSpec *pspec)
{
  AlsaSPDIFSink *sink;
 
  sink = ALSASPDIFSINK (object);
  
  switch (prop_id) {
  default:
    G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
    break;
  }
}


static GstPadLinkReturn
alsaspdifsink_link (GstPad *pad, const GstCaps *caps)
{
  AlsaSPDIFSink *sink = ALSASPDIFSINK (gst_pad_get_parent (pad));
  GstStructure *str;
  const gchar *mimetype;

  str = gst_caps_get_structure (caps, 0);

  mimetype = gst_structure_get_name (str);
  GST_DEBUG_OBJECT (sink, "mimetype: %s", mimetype);
  sink->passtrough = (strcmp(mimetype, "audio/x-iec958") == 0);

  GST_DEBUG_OBJECT (sink, "sinkpad linked, passtrough: %d",
                    sink->passtrough);

  if (GST_FLAG_IS_SET (sink, ALSASPDIFSINK_OPEN)) {
    alsaspdifsink_close (sink);
    alsaspdifsink_open (sink);
  }

  return GST_PAD_LINK_OK;
}


static gboolean
alsaspdifsink_open (AlsaSPDIFSink *sink)
{
  g_return_val_if_fail (!GST_FLAG_IS_SET (sink,
                                          ALSASPDIFSINK_OPEN), FALSE);

  sink->out_config.pcm_name = NULL;
  sink->out_config.card = "Live";
  sink->out_config.bits = 16;
  sink->out_config.rate = 48000;
  sink->out_config.channels = 2;
  sink->out_config.quiet = 0;
  sink->out_config.spdif = sink->passtrough ? SPDIF_CON : SPDIF_PCM;

  if (alsaspdifsink_alsa_open (sink) < 0) {
    return FALSE;
  }

  GST_FLAG_SET (sink, ALSASPDIFSINK_OPEN);

  return TRUE;
}


/**
 * Open the audio device for writing.
 */
static int
alsaspdifsink_alsa_open (AlsaSPDIFSink *sink)
{
  const char *pcm_name = sink->out_config.pcm_name;
  char devstr[128];
  snd_pcm_hw_params_t *params;
  unsigned int rate, buffer_time, period_time, tmp;
  snd_pcm_format_t format =
    sink->out_config.bits == 16 ? SND_PCM_FORMAT_S16 : SND_PCM_FORMAT_U8;
  int err, step;
  snd_pcm_hw_params_alloca (&params);

  GST_INFO_OBJECT (sink, "PCM name: %s", sink->out_config.pcm_name);
  GST_INFO_OBJECT (sink, "card: %s", sink->out_config.card);
  GST_INFO_OBJECT (sink, "bits: %d", sink->out_config.bits);
  GST_INFO_OBJECT (sink, "rate: %d", sink->out_config.rate);
  GST_INFO_OBJECT (sink, "channels: %d", sink->out_config.channels);
  GST_INFO_OBJECT (sink, "quiet: %d", sink->out_config.quiet);
  GST_INFO_OBJECT (sink, "SPDIF: %d", sink->out_config.spdif);

  if (pcm_name == NULL) {
    switch (sink->out_config.channels) {

    case 1:
    case 2:
      if (sink->out_config.spdif != SPDIF_NONE) {
        unsigned char s[4];
        if (sink->out_config.spdif == SPDIF_PRO) {
          s[0] = (IEC958_AES0_PROFESSIONAL |
                  IEC958_AES0_NONAUDIO |
                  IEC958_AES0_PRO_EMPHASIS_NONE |
                  IEC958_AES0_PRO_FS_48000);
          s[1] = (IEC958_AES1_PRO_MODE_NOTID |
                  IEC958_AES1_PRO_USERBITS_NOTID);
          s[2] = IEC958_AES2_PRO_WORDLEN_NOTID;
          s[3] = 0;
        }
        else {
          s[0] = IEC958_AES0_CON_EMPHASIS_NONE;
          if (sink->out_config.spdif == SPDIF_CON)
            s[0] |= IEC958_AES0_NONAUDIO;
          s[1] = (IEC958_AES1_CON_ORIGINAL |
                  IEC958_AES1_CON_PCM_CODER);
          s[2] = 0;
          s[3] = IEC958_AES3_CON_FS_48000;
        }

        sprintf (devstr,
                 "spdif:{AES0 0x%x AES1 0x%x AES2 0x%x AES3 0x%x",
                 s[0], s[1], s[2], s[3]);
        if (sink->out_config.card) {
          sprintf (devstr + strlen (devstr), " CARD %s",
                   sink->out_config.card);
        }
        strcat (devstr, "}");
        format = SND_PCM_FORMAT_S16_LE;
      }
      else {
        if (sink->out_config.card) {
          sprintf (devstr, "plughw:%s", sink->out_config.card);
        }
        else {
          sprintf (devstr, "default");
        }
      }
      break;

    case 4:
      strcpy (devstr, "plug:surround40");
      if (sink->out_config.card)
        sprintf (devstr + strlen (devstr), ":{CARD %s}",
                 sink->out_config.card);
      break;

    case 6:
      strcpy (devstr, "plug:surround51");
      if (sink->out_config.card)
        sprintf (devstr + strlen (devstr), ":{CARD %s}",
                 sink->out_config.card);
      break;

    default:
      g_return_val_if_reached (-EINVAL);
    }

    pcm_name = devstr;
  }

  if (!sink->out_config.quiet) {
    GST_INFO_OBJECT(sink, "Using PCM device '%s'", pcm_name);
  }

  err = snd_pcm_open (&(sink->pcm), pcm_name, SND_PCM_STREAM_PLAYBACK, 0);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("snd_pcm_open: %s", snd_strerror (err)),
                        GST_ERROR_SYSTEM);
    return err;
  }

  err = snd_pcm_hw_params_any (sink->pcm, params);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Broken configuration for this PCM: "
                        "no configurations available"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }

  /* Set interleaved access. */
  err = snd_pcm_hw_params_set_access (sink->pcm, params,
                                      SND_PCM_ACCESS_RW_INTERLEAVED);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Access type not available"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }

  err = snd_pcm_hw_params_set_format (sink->pcm, params, format);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Sample format not available"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }

  err = snd_pcm_hw_params_set_channels (sink->pcm, params,
                                        sink->out_config.channels);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Channels count not available"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }

  rate = sink->out_config.rate;
  err = snd_pcm_hw_params_set_rate_near (sink->pcm, params, &rate, 0);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Rate not available"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }

  buffer_time = 500000;
  err = snd_pcm_hw_params_set_buffer_time_near (sink->pcm, params,
                                                &buffer_time, 0);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Buffer time not available"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }
  GST_DEBUG_OBJECT (sink, "buffer size set to %0.3fs",
                    (double) buffer_time / 1000000);

  step = 2;
  period_time = 10000 * 2;
  do {
    period_time /= 2;
    tmp = period_time;

    err = snd_pcm_hw_params_set_period_time_near (sink->pcm, params, &tmp, 0);
    if (err < 0) {
      GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                         ("Period time not available"),
                         GST_ERROR_SYSTEM);
      goto __close;
    }

    if (tmp == period_time) {
      period_time /= 3;
      tmp = period_time;
      err = snd_pcm_hw_params_set_period_time_near (sink->pcm, params,
                                                    &tmp, 0);
      if (tmp == period_time) {
        period_time = 10000 * 2;
      }
    }
  } while (buffer_time == period_time && period_time > 10000);

  if (buffer_time == period_time) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("Buffer time and period time match, could not use"),
                       GST_ERROR_SYSTEM);
    goto __close;
  }

  err = snd_pcm_hw_params (sink->pcm, params);
  if (err < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("PCM hw_params failed: %s", snd_strerror (err)),
                        GST_ERROR_SYSTEM);
    goto __close;
  }

  return 0;
	
 __close:
  snd_pcm_close (sink->pcm);
  sink->pcm = NULL;
  return err;
}


static void
alsaspdifsink_close (AlsaSPDIFSink *sink)
{
  g_return_if_fail (GST_FLAG_IS_SET (sink, ALSASPDIFSINK_OPEN));

  snd_pcm_close (sink->pcm);

  GST_FLAG_UNSET (sink, ALSASPDIFSINK_OPEN);
}


static void
alsaspdifsink_write_samples (AlsaSPDIFSink *sink, gint16 *output_samples,
                             guint num_frames)
{
  snd_pcm_sframes_t res;

  res = 0;
  do {
    if (res == -EPIPE) {
      /* Underrun. */
      GST_DEBUG_OBJECT (sink, "buffer underrun");
      res = snd_pcm_prepare (sink->pcm);
    }
    else if (res == -ESTRPIPE) {
      /* Suspend. */
      while ((res = snd_pcm_resume (sink->pcm)) == -EAGAIN) {
        GST_DEBUG_OBJECT (sink, "sleeping for suspend");
        g_usleep (100000);
      }

      if (res < 0) {
        res = snd_pcm_prepare (sink->pcm);
      }
    }

    if (res >= 0) {
      res = snd_pcm_writei (sink->pcm, (void *)output_samples, num_frames);
    }

    if (res > 0) {
      output_samples += sink->out_config.channels * res;
      num_frames -= res;

      sink->clock_time +=  ALSASPDIFSINK_TIME_PER_FRAMES (sink, res);
    }

  } while (res == -EPIPE || num_frames > 0);

  if (res < 0) {
    GST_ELEMENT_ERROR (sink, RESOURCE, OPEN_WRITE,
                       ("writei returned error: %s", snd_strerror (res)),
                       GST_ERROR_SYSTEM);
    return;
  }
}


static GstClockTime
alsaspdifsink_get_time (GstClock *clock, gpointer data)
{
  AlsaSPDIFSink *sink = ALSASPDIFSINK (data);

  return sink->clock_time - alsaspdifsink_current_delay (sink);
}


static GstClock *
alsaspdifsink_get_clock (GstElement *element)
{
  AlsaSPDIFSink *sink = ALSASPDIFSINK (element);

  return sink->provided_clock;
}


static void
alsaspdifsink_set_clock (GstElement *element, GstClock *clock)
{
  AlsaSPDIFSink *sink = ALSASPDIFSINK (element);

  sink->clock = clock;
}


static GstClockTime
alsaspdifsink_current_delay (AlsaSPDIFSink *sink)
{
  snd_pcm_sframes_t delay;
  int err;

  err = snd_pcm_delay (sink->pcm, &delay);
  if (err < 0 || delay < 0) {
    return 0;
  }

  return ALSASPDIFSINK_TIME_PER_FRAMES (sink, delay);
}


static gboolean
alsaspdifsink_handle_event (GstPad *pad, GstEvent *event)
{
  GstEventType type;
  AlsaSPDIFSink *sink = ALSASPDIFSINK (gst_pad_get_parent (pad));

  type = event ? GST_EVENT_TYPE (event) : GST_EVENT_UNKNOWN;

  switch (type) {
  case GST_EVENT_FLUSH:
    GST_INFO_OBJECT (sink, "flush event received");

    alsaspdifsink_flush (sink);
    break;

  case GST_EVENT_DISCONTINUOUS:
    {
      GstClockTime time, delay;
	      
      if (gst_event_discont_get_value (event, GST_FORMAT_TIME, &time)) {
        delay = alsaspdifsink_current_delay (sink);
        gst_element_set_time_delay (GST_ELEMENT (sink), time, delay);
        sink->cur_ts = time;
        GST_INFO_OBJECT (sink,
            "handling discontinuity: time: %0.3fs, base: %0.3fs",
            (double) time / GST_SECOND,
            (double) GST_ELEMENT (sink)->base_time / GST_SECOND);
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
alsaspdifsink_chain (GstPad *pad, GstData *_data)
{
  GstBuffer *buf;
  AlsaSPDIFSink *sink;
  GstClockTime timestamp, next_write;

  g_return_if_fail (pad != NULL);
  g_return_if_fail (GST_IS_PAD (pad));
  g_return_if_fail (_data != NULL);

  if (GST_IS_EVENT (_data)) {
    alsaspdifsink_handle_event (pad, GST_EVENT (_data));
    return;
  }

  buf = GST_BUFFER (_data);
  sink = ALSASPDIFSINK (gst_pad_get_parent (pad));

  if (GST_FLAG_IS_SET (sink, ALSASPDIFSINK_OPEN)) {

    timestamp = GST_BUFFER_TIMESTAMP (buf);
    if (timestamp != GST_CLOCK_TIME_NONE) {
      GST_LOG_OBJECT (sink, "new timestamp: %0.3fs",
                      (double) timestamp / GST_SECOND);

#ifndef GST_DISABLE_GST_DEBUG
      if (ABS (GST_CLOCK_DIFF (timestamp, sink->cur_ts) > 1000)) {
        GST_DEBUG_OBJECT (sink, "internal sound discontinuity %0.4fs (%"
                          G_GINT64_FORMAT "), cur_ts: %0.3fs",
                          (double) GST_CLOCK_DIFF (timestamp, sink->cur_ts)
                          / GST_SECOND,
                          GST_CLOCK_DIFF (timestamp, sink->cur_ts),
                          (double) sink->cur_ts / GST_SECOND);
      }
#endif

      sink->cur_ts = timestamp;
    }

    next_write = gst_element_get_time (GST_ELEMENT (sink)) +
      alsaspdifsink_current_delay (sink);

/*     fprintf (stderr, "Drift: % 0.6fs, delay: % 0.6fs\r",  */
/*              (double) GST_CLOCK_DIFF (sink->cur_ts, next_write) / GST_SECOND, */
/*              (double) alsaspdifsink_current_delay (sink) / GST_SECOND); */

    if (sink->cur_ts > next_write + MAX_SYNC_DIFF) {
      static gint16 blank[1024 * 8];
      gint total_frames, blank_frames;

      total_frames =
        ALSASPDIFSINK_FRAMES_PER_TIME (sink, sink->cur_ts - next_write);
      blank_frames =
        (sizeof blank / snd_pcm_frames_to_bytes (sink->pcm, 1)) / 2;

      GST_DEBUG_OBJECT (sink, "playing %0.3fs silence (%d frames)",
                        (double) (sink->cur_ts - next_write)
                        / GST_SECOND, total_frames);

      snd_pcm_format_set_silence (SND_PCM_FORMAT_S16_LE, blank,
                                  blank_frames);

      while (total_frames > 0) {
        alsaspdifsink_write_samples (sink, blank,
                                     MIN(blank_frames, total_frames));

        total_frames -= blank_frames;
      }
    }
    else if (sink->cur_ts + MAX_SYNC_DIFF < next_write) {
      GST_DEBUG_OBJECT (sink, "skipping buffer for %0.3fs",
                        (double) (next_write - sink->cur_ts)
                        / GST_SECOND);
      goto end;
    }
  }

  alsaspdifsink_write_samples (sink,
                               (gint16 *) GST_BUFFER_DATA (buf),
                               GST_BUFFER_SIZE (buf) / 
                               ALSASPDIFSINK_BYTES_PER_FRAME (sink));

 end:
  sink->cur_ts +=  ALSASPDIFSINK_TIME_PER_FRAMES (sink,
                                     GST_BUFFER_SIZE (buf) /
                                     ALSASPDIFSINK_BYTES_PER_FRAME(sink));

  /* Update provided clock. */
  gst_audio_clock_update_time ((GstAudioClock *) sink->provided_clock,
                               alsaspdifsink_get_time (sink->provided_clock,
                                                       sink));

  gst_buffer_unref(buf);
}


static GstElementStateReturn
alsaspdifsink_change_state (GstElement *element)
{
  g_return_val_if_fail (GST_IS_ALSASPDIFSINK (element), GST_STATE_FAILURE);

  switch (GST_STATE_TRANSITION (element)) {
    case GST_STATE_NULL_TO_READY:
      if (!GST_FLAG_IS_SET (element, ALSASPDIFSINK_OPEN)) {
        if (!alsaspdifsink_open (ALSASPDIFSINK (element))) {
          return GST_STATE_FAILURE;
        }
      }
      break;
    case GST_STATE_READY_TO_PAUSED:
      break;
    case GST_STATE_PAUSED_TO_PLAYING:
      //snd_pcm_pause (ALSASPDIFSINK (element)->pcm, 0);
      gst_audio_clock_set_active (
          GST_AUDIO_CLOCK (ALSASPDIFSINK (element)->provided_clock),
          TRUE);
      break;
    case GST_STATE_PLAYING_TO_PAUSED:
      //snd_pcm_pause (ALSASPDIFSINK (element)->pcm, 1);
      gst_audio_clock_set_active (
          GST_AUDIO_CLOCK (ALSASPDIFSINK (element)->provided_clock),
          FALSE);
      break;
    case GST_STATE_PAUSED_TO_READY:
      break;
    case GST_STATE_READY_TO_NULL:
      if (GST_FLAG_IS_SET (element, ALSASPDIFSINK_OPEN)) {
        alsaspdifsink_close (ALSASPDIFSINK (element));
      }
      break;
  }

  GST_INFO_OBJECT (element, "time before: %0.3fs",
      (double) gst_element_get_time (element) / GST_SECOND);

  if (GST_ELEMENT_CLASS (parent_class)->change_state) {
    return GST_ELEMENT_CLASS (parent_class)->change_state (element);
  }

  GST_INFO_OBJECT (element, "time after: %0.3fs",
      (double) gst_element_get_time (element) / GST_SECOND);

  return GST_STATE_SUCCESS;
}


/**
 * alsaspdifsink_flush
 *
 * Clean up the sound device associated to this sink.
 */
static void
alsaspdifsink_flush (AlsaSPDIFSink *sink)
{
/*   int err; */

/*   err = snd_pcm_drop (sink->pcm); */
/*   if (err < 0) { */
/*     return; */
/*   } */

/*   err = snd_pcm_start (sink->pcm); */
/*   if (err < 0) { */
/*     GST_ELEMENT_ERROR (sink, RESOURCE, SEEK, */
/*                        ("snd_pcm_start: %s", snd_strerror (err)), */
/*                        GST_ERROR_SYSTEM); */
/*   } */
}
