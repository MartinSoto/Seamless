/* GStreamer
 * Copyright (C) <1999> Erik Walthinsen <omega@cse.ogi.edu>
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


/*#define GST_DEBUG_ENABLED*/
#ifdef HAVE_CONFIG_H
#include "config.h"
#endif
#include "gstmpegparse.h"
#include "gstmpegclock.h"

static GstFormat scr_format;


GST_DEBUG_CATEGORY_STATIC (gstmpegparse_debug);
#define GST_CAT_DEFAULT (gstmpegparse_debug)

GST_DEBUG_CATEGORY_EXTERN (GST_CAT_SEEK);


/* elementfactory information */
static GstElementDetails mpeg_parse_details = {
  "MPEG System Parser",
  "Codec/Parser",
  "Parses MPEG1 and MPEG2 System Streams",
  "Erik Walthinsen <omega@cse.ogi.edu>\n" "Wim Taymans <wim.taymans@chello.be>"
};

#define CLASS(o)	GST_MPEG_PARSE_CLASS (G_OBJECT_GET_CLASS (o))

#define DEFAULT_MAX_DISCONT	10000

/* GstMPEGParse signals and args */
enum
{
  /* FILL ME */
  LAST_SIGNAL
};

enum
{
  ARG_0,
  ARG_SYNC,
  ARG_MAX_DISCONT,
  ARG_DO_ADJUST
      /* FILL ME */
};

static GstStaticPadTemplate sink_factory = GST_STATIC_PAD_TEMPLATE ("sink",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/mpeg, "
        "mpegversion = (int) [ 1, 2 ], " "systemstream = (boolean) TRUE")
    );

static GstStaticPadTemplate src_factory = GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/mpeg, "
        "mpegversion = (int) [ 1, 2 ], " "systemstream = (boolean) TRUE")
    );

static void gst_mpeg_parse_class_init (GstMPEGParseClass * klass);
static void gst_mpeg_parse_base_init (GstMPEGParseClass * klass);
static void gst_mpeg_parse_init (GstMPEGParse * mpeg_parse);
static GstElementStateReturn gst_mpeg_parse_change_state (GstElement * element);

static void gst_mpeg_parse_set_clock (GstElement * element, GstClock * clock);

static gboolean gst_mpeg_parse_parse_packhead (GstMPEGParse * mpeg_parse,
    GstBuffer * buffer);

static void gst_mpeg_parse_handle_discont (GstMPEGParse * mpeg_parse,
    GstEvent * event);

static void gst_mpeg_parse_send_data (GstMPEGParse * mpeg_parse, GstData * data,
    GstClockTime time);
static void gst_mpeg_parse_send_discont (GstMPEGParse * mpeg_parse,
    GstClockTime time);

static void gst_mpeg_parse_new_pad (GstElement * element, GstPad * pad);

static void gst_mpeg_parse_loop (GstElement * element);

static void gst_mpeg_parse_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec);
static void gst_mpeg_parse_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec);
static void gst_mpeg_parse_set_index (GstElement * element, GstIndex * index);
static GstIndex *gst_mpeg_parse_get_index (GstElement * element);

static gboolean gst_mpeg_parse_release_locks (GstElement * element);

static GstElementClass *parent_class = NULL;

/*static guint gst_mpeg_parse_signals[LAST_SIGNAL] = { 0 };*/

GType
gst_mpeg_parse_get_type (void)
{
  static GType mpeg_parse_type = 0;

  if (!mpeg_parse_type) {
    static const GTypeInfo mpeg_parse_info = {
      sizeof (GstMPEGParseClass),
      (GBaseInitFunc) gst_mpeg_parse_base_init,
      NULL,
      (GClassInitFunc) gst_mpeg_parse_class_init,
      NULL,
      NULL,
      sizeof (GstMPEGParse),
      0,
      (GInstanceInitFunc) gst_mpeg_parse_init,
    };

    mpeg_parse_type =
        g_type_register_static (GST_TYPE_ELEMENT, "GstMPEGParse",
        &mpeg_parse_info, 0);

    GST_DEBUG_CATEGORY_INIT (gstmpegparse_debug, "mpegparse", 0,
        "MPEG parser element");
  }
  return mpeg_parse_type;
}

static void
gst_mpeg_parse_base_init (GstMPEGParseClass * klass)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (klass);

  gst_element_class_set_details (element_class, &mpeg_parse_details);
}

static void
gst_mpeg_parse_class_init (GstMPEGParseClass * klass)
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass *) klass;
  gstelement_class = (GstElementClass *) klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  g_object_class_install_property (G_OBJECT_CLASS (klass), ARG_SYNC,
      g_param_spec_boolean ("sync", "Sync", "Synchronize on the stream SCR",
          FALSE, G_PARAM_READWRITE));
  g_object_class_install_property (G_OBJECT_CLASS (klass), ARG_MAX_DISCONT,
      g_param_spec_int ("max_discont", "Max Discont",
          "The maximun allowed SCR discontinuity", 0, G_MAXINT,
          DEFAULT_MAX_DISCONT, G_PARAM_READWRITE));
  /* FIXME: Default is TRUE to make the behavior backwards compatible.
     It probably should be FALSE. */
  g_object_class_install_property (G_OBJECT_CLASS (klass), ARG_DO_ADJUST,
      g_param_spec_boolean ("adjust", "adjust", "Adjust timestamps to "
          "smooth discontinuities", TRUE, G_PARAM_READWRITE));

  gobject_class->get_property = gst_mpeg_parse_get_property;
  gobject_class->set_property = gst_mpeg_parse_set_property;

  gstelement_class->new_pad = gst_mpeg_parse_new_pad;
  gstelement_class->change_state = gst_mpeg_parse_change_state;
  gstelement_class->set_clock = gst_mpeg_parse_set_clock;
  gstelement_class->get_index = gst_mpeg_parse_get_index;
  gstelement_class->set_index = gst_mpeg_parse_set_index;
  gstelement_class->release_locks = gst_mpeg_parse_release_locks;

  klass->parse_packhead = gst_mpeg_parse_parse_packhead;
  klass->parse_syshead = NULL;
  klass->parse_packet = NULL;
  klass->parse_pes = NULL;
  klass->handle_discont = gst_mpeg_parse_handle_discont;
  klass->send_data = gst_mpeg_parse_send_data;
  klass->send_discont = gst_mpeg_parse_send_discont;

  /* FIXME: this is a hack.  We add the pad templates here instead
   * in the base_init function, since the derived class (mpegdemux)
   * uses different pads.  IMO, this is wrong. */
  gst_element_class_add_pad_template (gstelement_class,
      gst_static_pad_template_get (&src_factory));
  gst_element_class_add_pad_template (gstelement_class,
      gst_static_pad_template_get (&sink_factory));
}

static void
gst_mpeg_parse_init (GstMPEGParse * mpeg_parse)
{
  GstElementClass *klass = GST_ELEMENT_GET_CLASS (mpeg_parse);
  GstPadTemplate *templ;

  templ = gst_element_class_get_pad_template (klass, "sink");
  mpeg_parse->sinkpad = gst_pad_new_from_template (templ, "sink");
  gst_element_add_pad (GST_ELEMENT (mpeg_parse), mpeg_parse->sinkpad);
  gst_pad_set_formats_function (mpeg_parse->sinkpad,
      gst_mpeg_parse_get_src_formats);
  gst_pad_set_convert_function (mpeg_parse->sinkpad,
      gst_mpeg_parse_convert_src);

  if ((templ = gst_element_class_get_pad_template (klass, "src"))) {
    mpeg_parse->srcpad = gst_pad_new_from_template (templ, "src");
    gst_element_add_pad (GST_ELEMENT (mpeg_parse), mpeg_parse->srcpad);
    gst_pad_set_formats_function (mpeg_parse->srcpad,
        gst_mpeg_parse_get_src_formats);
    gst_pad_set_convert_function (mpeg_parse->srcpad,
        gst_mpeg_parse_convert_src);
    gst_pad_set_event_mask_function (mpeg_parse->srcpad,
        gst_mpeg_parse_get_src_event_masks);
    gst_pad_set_event_function (mpeg_parse->srcpad,
        gst_mpeg_parse_handle_src_event);
    gst_pad_set_query_type_function (mpeg_parse->srcpad,
        gst_mpeg_parse_get_src_query_types);
    gst_pad_set_query_function (mpeg_parse->srcpad,
        gst_mpeg_parse_handle_src_query);
    gst_pad_use_explicit_caps (mpeg_parse->srcpad);
  }

  gst_element_set_loop_function (GST_ELEMENT (mpeg_parse), gst_mpeg_parse_loop);

  mpeg_parse->packetize = NULL;
  mpeg_parse->sync = FALSE;
  mpeg_parse->id = NULL;
  mpeg_parse->max_discont = DEFAULT_MAX_DISCONT;

  mpeg_parse->do_adjust = TRUE;

  GST_FLAG_SET (mpeg_parse, GST_ELEMENT_EVENT_AWARE);
}

static void
gst_mpeg_parse_set_clock (GstElement * element, GstClock * clock)
{
  GstMPEGParse *parse = GST_MPEG_PARSE (element);

  parse->clock = clock;
}

#if 0
static void
gst_mpeg_parse_update_streaminfo (GstMPEGParse * mpeg_parse)
{
  GstProps *props;
  GstPropsEntry *entry;
  gboolean mpeg2 = GST_MPEG_PACKETIZE_IS_MPEG2 (mpeg_parse->packetize);
  GstCaps *caps;

  props = gst_props_empty_new ();

  entry = gst_props_entry_new ("mpegversion", G_TYPE_INT (mpeg2 ? 2 : 1));
  gst_props_add_entry (props, (GstPropsEntry *) entry);

  entry =
      gst_props_entry_new ("bitrate", G_TYPE_INT (mpeg_parse->mux_rate * 400));
  gst_props_add_entry (props, (GstPropsEntry *) entry);

  caps = gst_caps_new ("mpeg_streaminfo",
      "application/x-gst-streaminfo", props);

  gst_caps_replace_sink (&mpeg_parse->streaminfo, caps);
  g_object_notify (G_OBJECT (mpeg_parse), "streaminfo");
}
#endif

static void
gst_mpeg_parse_handle_discont (GstMPEGParse * mpeg_parse, GstEvent * event)
{
  GstClockTime time;

  g_return_if_fail (GST_EVENT_TYPE (event) == GST_EVENT_DISCONTINUOUS);

  if (gst_event_discont_get_value (event, GST_FORMAT_TIME, &time)) {
    GST_DEBUG_OBJECT (mpeg_parse,
        "forwarding discontinuity, time: %0.3fs", (double) time / GST_SECOND);

    if (CLASS (mpeg_parse)->send_discont)
      CLASS (mpeg_parse)->send_discont (mpeg_parse, time);
  }
  mpeg_parse->packetize->resync = TRUE;

  gst_event_unref (event);
}

static void
gst_mpeg_parse_send_data (GstMPEGParse * mpeg_parse, GstData * data,
    GstClockTime time)
{
  if (GST_IS_EVENT (data)) {
    GstEvent *event = GST_EVENT (data);

    switch (GST_EVENT_TYPE (event)) {
      default:
        gst_pad_event_default (mpeg_parse->sinkpad, event);
        break;
    }
  } else {
    if (!gst_pad_is_negotiated (mpeg_parse->srcpad)) {
      gboolean mpeg2 = GST_MPEG_PACKETIZE_IS_MPEG2 (mpeg_parse->packetize);
      GstCaps *caps;

      caps = gst_caps_new_simple ("video/mpeg",
          "mpegversion", G_TYPE_INT, (mpeg2 ? 2 : 1),
          "systemstream", G_TYPE_BOOLEAN, TRUE,
          "parsed", G_TYPE_BOOLEAN, TRUE, NULL);

      if (!gst_pad_set_explicit_caps (mpeg_parse->srcpad, caps)) {
        GST_ELEMENT_ERROR (GST_ELEMENT (mpeg_parse),
            CORE, NEGOTIATION, (NULL), ("failed to set caps"));
        return;
      }
    }

    GST_BUFFER_TIMESTAMP (data) = time;
    GST_DEBUG ("current_scr %" G_GINT64_FORMAT, time);

    if (GST_PAD_IS_USABLE (mpeg_parse->srcpad))
      gst_pad_push (mpeg_parse->srcpad, GST_DATA (data));
    else
      gst_data_unref (data);
  }
}

static void
gst_mpeg_parse_send_discont (GstMPEGParse * mpeg_parse, GstClockTime time)
{
  GstEvent *event;

  if (GST_PAD_IS_USABLE (mpeg_parse->srcpad)) {
    event = gst_event_new_discontinuous (FALSE, GST_FORMAT_TIME, time, NULL);
    gst_pad_push (mpeg_parse->srcpad, GST_DATA (event));
  }
}

static void
gst_mpeg_parse_new_pad (GstElement * element, GstPad * pad)
{
  GstMPEGParse *mpeg_parse;

  if (GST_PAD_IS_SINK (pad))
    return;

  mpeg_parse = GST_MPEG_PARSE (element);

  /* For each new added pad, send a discont so it knows about the current
   * time. This is required because MPEG allows any sort of order of
   * packets, including setting base time before defining streams or
   * even adding streams halfway a stream. */
  if (!mpeg_parse->scr_pending && !mpeg_parse->do_adjust) {
    GstEvent *event = gst_event_new_discontinuous (FALSE,
        GST_FORMAT_TIME,
        (guint64) MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr +
            mpeg_parse->adjust),
        GST_FORMAT_UNDEFINED);

    gst_pad_push (pad, GST_DATA (event));
  }
}

static gboolean
gst_mpeg_parse_parse_packhead (GstMPEGParse * mpeg_parse, GstBuffer * buffer)
{
  guint8 *buf;
  guint64 prev_scr, scr;
  guint32 scr1, scr2;
  guint32 new_rate;

  buf = GST_BUFFER_DATA (buffer);
  buf += 4;

  scr1 = GUINT32_FROM_BE (*(guint32 *) buf);
  scr2 = GUINT32_FROM_BE (*(guint32 *) (buf + 4));

  if (GST_MPEG_PACKETIZE_IS_MPEG2 (mpeg_parse->packetize)) {
    guint32 scr_ext;

    /* :2=01 ! scr:3 ! marker:1==1 ! scr:15 ! marker:1==1 ! scr:15 */
    scr = ((guint64) scr1 & 0x38000000) << 3;
    scr |= ((guint64) scr1 & 0x03fff800) << 4;
    scr |= ((guint64) scr1 & 0x000003ff) << 5;
    scr |= ((guint64) scr2 & 0xf8000000) >> 27;

    scr_ext = (scr2 & 0x03fe0000) >> 17;

    scr = (scr * 300 + scr_ext % 300) / 300;

    GST_LOG_OBJECT (mpeg_parse, "%" G_GINT64_FORMAT " %d, %08x %08x %"
        G_GINT64_FORMAT " diff: %" G_GINT64_FORMAT,
        scr, scr_ext, scr1, scr2, mpeg_parse->bytes_since_scr,
        scr - mpeg_parse->current_scr);

    buf += 6;
    new_rate = (GUINT32_FROM_BE ((*(guint32 *) buf)) & 0xfffffc00) >> 10;
  } else {
    scr = ((guint64) scr1 & 0x0e000000) << 5;
    scr |= ((guint64) scr1 & 0x00fffe00) << 6;
    scr |= ((guint64) scr1 & 0x000000ff) << 7;
    scr |= ((guint64) scr2 & 0xfe000000) >> 25;

    buf += 5;
    /* we do this byte by byte because buf[3] might be outside of buf's
     * memory space */
    new_rate = ((gint32) buf[0] & 0x7f) << 15;
    new_rate |= ((gint32) buf[1]) << 7;
    new_rate |= buf[2] >> 1;
  }

  prev_scr = mpeg_parse->current_scr;
  mpeg_parse->current_scr = scr;
  mpeg_parse->scr_pending = FALSE;

  if (mpeg_parse->next_scr == -1) {
    mpeg_parse->next_scr = mpeg_parse->current_scr;
  }

  GST_LOG_OBJECT (mpeg_parse,
      "SCR is %" G_GUINT64_FORMAT
      " (%" G_GUINT64_FORMAT ") next: %"
      G_GINT64_FORMAT " (%" G_GINT64_FORMAT
      ") diff: %" G_GINT64_FORMAT " (%"
      G_GINT64_FORMAT ")",
      mpeg_parse->current_scr,
      MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr),
      mpeg_parse->next_scr,
      MPEGTIME_TO_GSTTIME (mpeg_parse->next_scr),
      mpeg_parse->current_scr - mpeg_parse->next_scr,
      MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr) -
      MPEGTIME_TO_GSTTIME (mpeg_parse->next_scr));

  if (ABS ((gint64) mpeg_parse->next_scr - (gint64) (scr)) >
      mpeg_parse->max_discont) {
    GST_DEBUG ("discontinuity detected; expected: %" G_GUINT64_FORMAT " got: %"
        G_GUINT64_FORMAT " real:%" G_GINT64_FORMAT " adjust:%" G_GINT64_FORMAT,
        mpeg_parse->next_scr, mpeg_parse->current_scr + mpeg_parse->adjust,
        mpeg_parse->current_scr, mpeg_parse->adjust);

    if (mpeg_parse->do_adjust) {
      mpeg_parse->adjust +=
          (gint64) mpeg_parse->next_scr - (gint64) mpeg_parse->current_scr;

      GST_DEBUG ("new adjust: %" G_GINT64_FORMAT, mpeg_parse->adjust);
    }
#if 0
    } else {
      mpeg_parse->discont_pending = TRUE;
    }
#endif
  }

  if (mpeg_parse->index && GST_INDEX_IS_WRITABLE (mpeg_parse->index)) {
    /* update index if any */
    gst_index_add_association (mpeg_parse->index, mpeg_parse->index_id,
        GST_ASSOCIATION_FLAG_KEY_UNIT,
        GST_FORMAT_BYTES, GST_BUFFER_OFFSET (buffer),
        GST_FORMAT_TIME, MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr), 0);
  }

  if (mpeg_parse->mux_rate != new_rate) {
    mpeg_parse->mux_rate =
        (double) mpeg_parse->bytes_since_scr /
        MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr -
        prev_scr) / 50 * 1000000000;

    //gst_mpeg_parse_update_streaminfo (mpeg_parse);
    GST_DEBUG ("stream is %1.3fMbs", (mpeg_parse->mux_rate * 400) / 1000000.0);
  }
  mpeg_parse->bytes_since_scr = 0;

  return TRUE;
}

static void
gst_mpeg_parse_loop (GstElement * element)
{
  GstMPEGParse *mpeg_parse = GST_MPEG_PARSE (element);
  GstData *data;
  guint id;
  gboolean mpeg2;
  GstClockTime time;

  data = gst_mpeg_packetize_read (mpeg_parse->packetize);
  if (!data)
    return;

  id = GST_MPEG_PACKETIZE_ID (mpeg_parse->packetize);
  mpeg2 = GST_MPEG_PACKETIZE_IS_MPEG2 (mpeg_parse->packetize);

  if (GST_IS_BUFFER (data)) {
    GstBuffer *buffer = GST_BUFFER (data);

    GST_LOG_OBJECT (mpeg_parse, "have chunk 0x%02X", id);

    switch (id) {
      case 0xb9:
        break;
      case 0xba:
        if (CLASS (mpeg_parse)->parse_packhead) {
          CLASS (mpeg_parse)->parse_packhead (mpeg_parse, buffer);
        }
        break;
      case 0xbb:
        if (CLASS (mpeg_parse)->parse_syshead) {
          CLASS (mpeg_parse)->parse_syshead (mpeg_parse, buffer);
        }
        break;
      default:
        if (mpeg2 && ((id < 0xBD) || (id > 0xFE))) {
          g_warning ("******** unknown id 0x%02X", id);
        } else {
          if (mpeg2) {
            if (CLASS (mpeg_parse)->parse_pes) {
              CLASS (mpeg_parse)->parse_pes (mpeg_parse, buffer);
            }
          } else {
            if (CLASS (mpeg_parse)->parse_packet) {
              CLASS (mpeg_parse)->parse_packet (mpeg_parse, buffer);
            }
          }
        }
    }
  }

  time = MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr);

  if (GST_IS_EVENT (data)) {
    GstEvent *event = GST_EVENT (data);

    switch (GST_EVENT_TYPE (event)) {
      case GST_EVENT_DISCONTINUOUS:
        if (CLASS (mpeg_parse)->handle_discont)
          CLASS (mpeg_parse)->handle_discont (mpeg_parse, event);
        return;
      default:
        break;
    }
    if (CLASS (mpeg_parse)->send_data)
      CLASS (mpeg_parse)->send_data (mpeg_parse, data, time);
    else
      gst_event_unref (event);
  } else {
    guint64 size;

    /* we're not sending data as long as no new SCR was found */
    if (mpeg_parse->discont_pending) {
      if (!mpeg_parse->scr_pending) {
        if (mpeg_parse->clock && mpeg_parse->sync) {
          gst_element_set_time (GST_ELEMENT (mpeg_parse),
              MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr));
        }
        if (CLASS (mpeg_parse)->send_discont) {
          CLASS (mpeg_parse)->send_discont (mpeg_parse,
              MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr +
                  mpeg_parse->adjust));
        }
        mpeg_parse->discont_pending = FALSE;
      } else {
        GST_DEBUG ("waiting for SCR");
        gst_buffer_unref (GST_BUFFER (data));
        return;
      }
    }

    size = GST_BUFFER_SIZE (data);
    mpeg_parse->bytes_since_scr += size;

    if (!GST_PAD_CAPS (mpeg_parse->sinkpad)) {
      gboolean mpeg2 = GST_MPEG_PACKETIZE_IS_MPEG2 (mpeg_parse->packetize);

      if (gst_pad_try_set_caps (mpeg_parse->sinkpad,
              gst_caps_new_simple ("video/mpeg",
                  "mpegversion", G_TYPE_INT, (mpeg2 ? 2 : 1),
                  "systemstream", G_TYPE_BOOLEAN, TRUE,
                  "parsed", G_TYPE_BOOLEAN, TRUE, NULL)) < 0) {
        GST_ELEMENT_ERROR (mpeg_parse, CORE, NEGOTIATION, (NULL), (NULL));
        return;
      }
    }

    if (CLASS (mpeg_parse)->send_data)
      CLASS (mpeg_parse)->send_data (mpeg_parse, data, time);

    if (mpeg_parse->clock && mpeg_parse->sync && !mpeg_parse->discont_pending) {
      GST_DEBUG ("syncing mpegparse");
      gst_element_wait (GST_ELEMENT (mpeg_parse), time);
    }

    if (mpeg_parse->current_scr != -1) {
      guint64 scr, bss, br;

      scr = mpeg_parse->current_scr;
      bss = mpeg_parse->bytes_since_scr;
      br = mpeg_parse->mux_rate * 50;

      if (br) {
        if (GST_MPEG_PACKETIZE_IS_MPEG2 (mpeg_parse->packetize)) {
          /* 
           * The mpeg spec says something like this, but that doesn't really work:
           *
           * mpeg_parse->next_scr = (scr * br + bss * CLOCK_FREQ) / (CLOCK_FREQ + br);
           */
          mpeg_parse->next_scr = scr + (bss * CLOCK_FREQ) / br;
        } else {
          /* we are interpolating the scr here */
          mpeg_parse->next_scr = scr + (bss * CLOCK_FREQ) / br;
        }
      } else {
        /* no bitrate known */
        mpeg_parse->next_scr = scr;
      }

      GST_LOG_OBJECT (mpeg_parse, "size: %" G_GINT64_FORMAT
          ", total since SCR: %" G_GINT64_FORMAT
          ", next SCR: %" G_GINT64_FORMAT, size, bss, mpeg_parse->next_scr);
    }
  }
}

const GstFormat *
gst_mpeg_parse_get_src_formats (GstPad * pad)
{
  static const GstFormat formats[] = {
    GST_FORMAT_BYTES,
    GST_FORMAT_TIME,
    0
  };

  return formats;
}

gboolean
gst_mpeg_parse_convert_src (GstPad * pad, GstFormat src_format,
    gint64 src_value, GstFormat * dest_format, gint64 * dest_value)
{
  gboolean res = TRUE;
  GstMPEGParse *mpeg_parse = GST_MPEG_PARSE (gst_pad_get_parent (pad));

  switch (src_format) {
    case GST_FORMAT_BYTES:
      switch (*dest_format) {
        case GST_FORMAT_DEFAULT:
          *dest_format = GST_FORMAT_TIME;
        case GST_FORMAT_TIME:
          if (mpeg_parse->mux_rate == 0)
            res = FALSE;
          else
            *dest_value = src_value * GST_SECOND / (mpeg_parse->mux_rate * 50);
          break;
        default:
          res = FALSE;
      }
      break;
    case GST_FORMAT_TIME:
      switch (*dest_format) {
        case GST_FORMAT_DEFAULT:
          *dest_format = GST_FORMAT_BYTES;
        case GST_FORMAT_BYTES:
          *dest_value = mpeg_parse->mux_rate * 50 * src_value / GST_SECOND;
          break;
        default:
          res = FALSE;
      }
      break;
    default:
      res = FALSE;
      break;
  }
  return res;
}

const GstQueryType *
gst_mpeg_parse_get_src_query_types (GstPad * pad)
{
  static const GstQueryType types[] = {
    GST_QUERY_TOTAL,
    GST_QUERY_POSITION,
    0
  };

  return types;
}

gboolean
gst_mpeg_parse_handle_src_query (GstPad * pad, GstQueryType type,
    GstFormat * format, gint64 * value)
{
  gboolean res = TRUE;
  GstMPEGParse *mpeg_parse = GST_MPEG_PARSE (gst_pad_get_parent (pad));
  GstFormat src_format;
  gint64 src_value;

  switch (type) {
    case GST_QUERY_TOTAL:
    {
      switch (*format) {
        case GST_FORMAT_DEFAULT:
          *format = GST_FORMAT_TIME;
          /* fallthrough */
        default:
          src_format = GST_FORMAT_BYTES;
          if (!gst_pad_query (GST_PAD_PEER (mpeg_parse->sinkpad),
                  GST_QUERY_TOTAL, &src_format, &src_value)) {
            res = FALSE;
          }
          break;
      }
      break;
    }
    case GST_QUERY_POSITION:
    {
      switch (*format) {
        case GST_FORMAT_DEFAULT:
          *format = GST_FORMAT_TIME;
          /* fallthrough */
        default:
          src_format = GST_FORMAT_TIME;
          src_value = MPEGTIME_TO_GSTTIME (mpeg_parse->current_scr);
          break;
      }
      break;
    }
    default:
      res = FALSE;
      break;
  }

  /* bring to requested format */
  if (res)
    res = gst_pad_convert (pad, src_format, src_value, format, value);

  return res;
}

const GstEventMask *
gst_mpeg_parse_get_src_event_masks (GstPad * pad)
{
  static const GstEventMask masks[] = {
    {GST_EVENT_SEEK, GST_SEEK_METHOD_SET | GST_SEEK_FLAG_FLUSH},
    {0,}
  };

  return masks;
}

static gboolean
index_seek (GstPad * pad, GstEvent * event, guint64 * offset, gint64 * scr)
{
  GstIndexEntry *entry;
  GstMPEGParse *mpeg_parse = GST_MPEG_PARSE (gst_pad_get_parent (pad));

  entry = gst_index_get_assoc_entry (mpeg_parse->index, mpeg_parse->index_id,
      GST_INDEX_LOOKUP_BEFORE, 0,
      GST_EVENT_SEEK_FORMAT (event), GST_EVENT_SEEK_OFFSET (event));
  if (!entry)
    return FALSE;

  if (gst_index_entry_assoc_map (entry, GST_FORMAT_BYTES, offset)) {
    gint64 time;

    if (gst_index_entry_assoc_map (entry, GST_FORMAT_TIME, &time)) {
      *scr = GSTTIME_TO_MPEGTIME (time);
    }
    GST_CAT_DEBUG (GST_CAT_SEEK, "%s:%s index %s %" G_GINT64_FORMAT
        " -> %" G_GINT64_FORMAT " bytes, scr=%" G_GINT64_FORMAT,
        GST_DEBUG_PAD_NAME (pad),
        gst_format_get_details (GST_EVENT_SEEK_FORMAT (event))->nick,
        GST_EVENT_SEEK_OFFSET (event), *offset, *scr);
    return TRUE;
  }
  return FALSE;
}

static gboolean
normal_seek (GstPad * pad, GstEvent * event, guint64 * offset, gint64 * scr)
{
  gboolean res;
  GstFormat format;
  gint64 time;

  /* bring offset to bytes */
  format = GST_FORMAT_BYTES;
  res = gst_pad_convert (pad,
      GST_EVENT_SEEK_FORMAT (event),
      GST_EVENT_SEEK_OFFSET (event), &format, offset);
  /* bring offset to time */
  format = GST_FORMAT_TIME;
  res &= gst_pad_convert (pad,
      GST_EVENT_SEEK_FORMAT (event),
      GST_EVENT_SEEK_OFFSET (event), &format, &time);

  /* convert to scr */
  *scr = GSTTIME_TO_MPEGTIME (time);

  return res;
}

gboolean
gst_mpeg_parse_handle_src_event (GstPad * pad, GstEvent * event)
{
  gboolean res = FALSE;
  GstMPEGParse *mpeg_parse = GST_MPEG_PARSE (gst_pad_get_parent (pad));

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_SEEK:
    {
      guint64 desired_offset;
      guint64 expected_scr;

      /* first to to use the index if we have one */
      if (mpeg_parse->index)
        res = index_seek (pad, event, &desired_offset, &expected_scr);
      /* nothing found, try fuzzy seek */
      if (!res)
        res = normal_seek (pad, event, &desired_offset, &expected_scr);

      if (!res)
        break;

      GST_DEBUG ("sending seek to %" G_GINT64_FORMAT, desired_offset);
      if (gst_bytestream_seek (mpeg_parse->packetize->bs, desired_offset,
              GST_SEEK_METHOD_SET)) {
        mpeg_parse->discont_pending = TRUE;
        mpeg_parse->scr_pending = TRUE;
        mpeg_parse->next_scr = expected_scr;
        mpeg_parse->current_scr = -1;
        mpeg_parse->adjust = 0;
        res = TRUE;
      }
      break;
    }
    default:
      break;
  }
  gst_event_unref (event);
  return res;
}

static GstElementStateReturn
gst_mpeg_parse_change_state (GstElement * element)
{
  GstMPEGParse *mpeg_parse = GST_MPEG_PARSE (element);

  switch (GST_STATE_TRANSITION (element)) {
    case GST_STATE_READY_TO_PAUSED:
      if (!mpeg_parse->packetize) {
        mpeg_parse->packetize =
            gst_mpeg_packetize_new (mpeg_parse->sinkpad,
            GST_MPEG_PACKETIZE_SYSTEM);
      }
      /* initialize parser state */
      mpeg_parse->current_scr = 0;
      mpeg_parse->bytes_since_scr = 0;
      mpeg_parse->adjust = 0;
      mpeg_parse->next_scr = 0;

      /* zero counters (should be done at RUNNING?) */
      mpeg_parse->mux_rate = 0;
      mpeg_parse->discont_pending = FALSE;
      mpeg_parse->scr_pending = FALSE;
      break;
    case GST_STATE_PAUSED_TO_READY:
      if (mpeg_parse->packetize) {
        gst_mpeg_packetize_destroy (mpeg_parse->packetize);
        mpeg_parse->packetize = NULL;
      }
      //gst_caps_replace (&mpeg_parse->streaminfo, NULL);
      break;
    default:
      break;
  }

  return GST_ELEMENT_CLASS (parent_class)->change_state (element);
}

static void
gst_mpeg_parse_get_property (GObject * object, guint prop_id, GValue * value,
    GParamSpec * pspec)
{
  GstMPEGParse *mpeg_parse;

  mpeg_parse = GST_MPEG_PARSE (object);

  switch (prop_id) {
    case ARG_SYNC:
      g_value_set_boolean (value, mpeg_parse->sync);
      break;
    case ARG_MAX_DISCONT:
      g_value_set_int (value, mpeg_parse->max_discont);
      break;
    case ARG_DO_ADJUST:
      g_value_set_boolean (value, mpeg_parse->do_adjust);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

static void
gst_mpeg_parse_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec)
{
  GstMPEGParse *mpeg_parse;

  mpeg_parse = GST_MPEG_PARSE (object);

  switch (prop_id) {
    case ARG_SYNC:
      mpeg_parse->sync = g_value_get_boolean (value);
      break;
    case ARG_MAX_DISCONT:
      mpeg_parse->max_discont = g_value_get_int (value);
      break;
    case ARG_DO_ADJUST:
      mpeg_parse->do_adjust = g_value_get_boolean (value);
      mpeg_parse->adjust = 0;
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

static void
gst_mpeg_parse_set_index (GstElement * element, GstIndex * index)
{
  GstMPEGParse *mpeg_parse;

  mpeg_parse = GST_MPEG_PARSE (element);

  mpeg_parse->index = index;

  gst_index_get_writer_id (index, GST_OBJECT (mpeg_parse->sinkpad),
      &mpeg_parse->index_id);
  gst_index_add_format (index, mpeg_parse->index_id, scr_format);
}

static GstIndex *
gst_mpeg_parse_get_index (GstElement * element)
{
  GstMPEGParse *mpeg_parse;

  mpeg_parse = GST_MPEG_PARSE (element);

  return mpeg_parse->index;
}

static gboolean
gst_mpeg_parse_release_locks (GstElement * element)
{
  GstMPEGParse *mpeg_parse;

  mpeg_parse = GST_MPEG_PARSE (element);

  if (mpeg_parse->id) {
    /* FIXME */
    //gst_clock_id_unlock (mpeg_parse->id);
  }

  return TRUE;
}

gboolean
gst_mpeg_parse_plugin_init (GstPlugin * plugin)
{
  scr_format =
      gst_format_register ("scr", "The MPEG system clock reference time");

  return gst_element_register (plugin, "seamless-mpegparse",
      GST_RANK_NONE, GST_TYPE_MPEG_PARSE);
}
