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

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <string.h>

#include "gstmpeg2subt.h"


GST_DEBUG_CATEGORY_STATIC (mpeg2subt_debug);
#define GST_CAT_DEFAULT (mpeg2subt_debug)


/* Convert SPU decoder delays to GStreamer time. */
#define DELAY_TO_GST(delay) ((GST_MSECOND * 1024 * (delay)) / 90)


/* Small numerical errors could happen when converting delays from
   MPEG to GStreamer, so we allow for a small difference when
   comparing values: */
#define COMPARE_GAP ((2 * GST_SECOND) / 90)

/* Maximum number of frames to adjust before giving up. */
#define MAX_ADJUST 5


/* elementfactory information */
static GstElementDetails mpeg2subt_details = {
  "MPEG2 subtitle Decoder",
  "Codec/Decoder/Video",
  "Decodes and merges MPEG2 subtitles into a video frame",
  "Wim Taymans <wim.taymans@chello.be>\n"
      "Jan Schmidt <thaytan@mad.scientist.com>\n"
      "Martin Soto <martinsoto@users.sourceforge.net>"
};


/* GstMpeg2Subt signals and args */
enum
{
  /* FILL ME */
  LAST_SIGNAL
};

enum
{
  ARG_0,
  ARG_SKIP
      /* FILL ME */
};


static GstStaticPadTemplate video_template = GST_STATIC_PAD_TEMPLATE ("video",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/x-raw-yuv, " "format = (fourcc) { I420 }, "
		     /* YV12 later */
        "width = (int) [ 16, 4096 ], " "height = (int) [ 16, 4096 ]")
    );

static GstStaticPadTemplate src_template = GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/x-raw-yuv, " "format = (fourcc) { I420 }, "
		     /* YV12 later */
        "width = (int) [ 16, 4096 ], " "height = (int) [ 16, 4096 ]")
    );

static GstStaticPadTemplate subtitle_template =
GST_STATIC_PAD_TEMPLATE ("subtitle",
    GST_PAD_SINK,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS ("video/x-dvd-subpicture")
    );

enum
{
  SPU_FORCE_DISPLAY = 0x00,
  SPU_SHOW = 0x01,
  SPU_HIDE = 0x02,
  SPU_SET_PALETTE = 0x03,
  SPU_SET_ALPHA = 0x04,
  SPU_SET_SIZE = 0x05,
  SPU_SET_OFFSETS = 0x06,
  SPU_WIPE = 0x07,
  SPU_END = 0xff
};

typedef struct RLE_state
{
  gint id;
  gint aligned;
  gint offset[2];
  gint clip_left;
  gint clip_top;
  gint clip_right;
  gint clip_bottom;

  guchar *target_Y;
  guchar *target_U;
  guchar *target_V;
  guchar *target_A;

  guchar next;

  gint y;
}
RLE_state;


#define _do_init(bla) \
    GST_DEBUG_CATEGORY_INIT (mpeg2subt_debug, "mpeg2subt", 0, \
        "MPEG2 subtitle overlay element");

GST_BOILERPLATE_FULL (GstMpeg2Subt, gst_mpeg2subt, GstElement, GST_TYPE_ELEMENT,
    _do_init);


static void gst_mpeg2subt_class_init (GstMpeg2SubtClass * gclass);

static GstCaps *gst_mpeg2subt_getcaps (GstPad * pad);
static GstPadLinkReturn gst_mpeg2subt_setcaps (GstPad * pad,
    GstCaps * caps);
static gboolean gst_mpeg2subt_src_activate_push (GstPad * pad,
    gboolean active);
static GstFlowReturn gst_mpeg2subt_chain_video (GstPad * pad,
    GstBuffer * buffer);
static void gst_mpeg2subt_loop (GstMpeg2Subt * mpeg2subt);
static gboolean gst_mpeg2subt_event_video (GstPad *pad, GstEvent *event);

static void gst_mpeg2subt_execute_block (GstMpeg2Subt * mpeg2subt);
static void gst_mpeg2subt_update (GstMpeg2Subt * mpeg2subt,
				  GstClockTime time);
static gboolean gst_mpeg2subt_src_event (GstPad * pad, GstEvent * event);
static GstFlowReturn gst_mpeg2subt_chain_subtitle (GstPad * pad,
    GstBuffer * buffer);
static gboolean gst_mpeg2subt_event_subtitle (GstPad *pad, GstEvent *event);

static void gst_mpeg2subt_merge_title (GstMpeg2Subt * mpeg2subt,
    GstBuffer * buf);
static void gst_mpeg2subt_reset_highlight (GstMpeg2Subt * mpeg2subt);
static gboolean gst_mpeg2subt_handle_dvd_event (GstMpeg2Subt * mpeg2subt,
    GstEvent * event, gboolean from_sub_pad);
static void gst_mpeg2subt_finalize (GObject * gobject);
static void gst_mpeg2subt_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec);
static void gst_mpeg2subt_get_property (GObject * object, guint prop_id,
    GValue * value, GParamSpec * pspec);
static void gst_mpeg2subt_setup_palette (GstMpeg2Subt * mpeg2subt);
static void gst_mpeg2subt_setup_highlight_palette (GstMpeg2Subt * mpeg2subt);


/*static guint gst_mpeg2subt_signals[LAST_SIGNAL] = { 0 };*/


static void
gst_mpeg2subt_base_init (gpointer gclass)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (gclass);

  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&src_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&video_template));
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&subtitle_template));

  gst_element_class_set_details (element_class, &mpeg2subt_details);
}

static void
gst_mpeg2subt_class_init (GstMpeg2SubtClass * gclass)
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass *) gclass;
  gstelement_class = (GstElementClass *) gclass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  gobject_class->set_property = gst_mpeg2subt_set_property;
  gobject_class->get_property = gst_mpeg2subt_get_property;
  gobject_class->finalize = gst_mpeg2subt_finalize;

  /* CHECKME: */
  g_object_class_install_property (G_OBJECT_CLASS (gclass), ARG_SKIP,
				   g_param_spec_int ("skip", "skip",
						     "skip", G_MININT,
						     G_MAXINT, 0,
						     G_PARAM_READWRITE));
}

static void
gst_mpeg2subt_init (GstMpeg2Subt * mpeg2subt, GstMpeg2SubtClass * gclass)
{
  mpeg2subt->lock = g_mutex_new ();

  mpeg2subt->videopad =
      gst_pad_new_from_template (gst_static_pad_template_get
      (&video_template), "video");
  gst_element_add_pad (GST_ELEMENT (mpeg2subt), mpeg2subt->videopad);
  gst_pad_set_setcaps_function (mpeg2subt->videopad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_setcaps));
  gst_pad_set_getcaps_function (mpeg2subt->videopad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_getcaps));
  gst_pad_set_chain_function (mpeg2subt->videopad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_chain_video));
  gst_pad_set_event_function (mpeg2subt->videopad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_event_video));

  mpeg2subt->subtitlepad =
      gst_pad_new_from_template (gst_static_pad_template_get
      (&subtitle_template), "subtitle");
  gst_element_add_pad (GST_ELEMENT (mpeg2subt), mpeg2subt->subtitlepad);
  gst_pad_set_chain_function (mpeg2subt->subtitlepad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_chain_subtitle));
  gst_pad_set_event_function (mpeg2subt->subtitlepad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_event_subtitle));

  mpeg2subt->srcpad =
      gst_pad_new_from_template (gst_static_pad_template_get
      (&src_template), "src");
  gst_element_add_pad (GST_ELEMENT (mpeg2subt), mpeg2subt->srcpad);
  gst_pad_set_getcaps_function (mpeg2subt->srcpad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_getcaps));
  gst_pad_set_setcaps_function (mpeg2subt->srcpad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_setcaps));
  gst_pad_set_event_function (mpeg2subt->srcpad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_src_event));
  gst_pad_set_activatepush_function (mpeg2subt->srcpad,
      GST_DEBUG_FUNCPTR (gst_mpeg2subt_src_activate_push));

  mpeg2subt->data = NULL;
  mpeg2subt->data_received = g_cond_new();
  mpeg2subt->data_processed = g_cond_new();

  mpeg2subt->partialbuf = NULL;
  mpeg2subt->subt_queue = g_queue_new ();

  mpeg2subt->last_frame = NULL;

  mpeg2subt->cur_cmds = NULL;
  mpeg2subt->cur_cmds_buf = NULL;
  mpeg2subt->cur_cmds_time = GST_CLOCK_TIME_NONE;

  mpeg2subt->current_buf = NULL;
  mpeg2subt->display = FALSE;
  mpeg2subt->hide = FALSE;
  mpeg2subt->forced_display = FALSE;

  mpeg2subt->still = FALSE;
  mpeg2subt->still_ts = GST_CLOCK_TIME_NONE;
  mpeg2subt->still_stop = GST_CLOCK_TIME_NONE;

  mpeg2subt->last_video_ts = GST_CLOCK_TIME_NONE;
  mpeg2subt->adjusted_count = 0;

  memset (mpeg2subt->current_clut, 0, 16 * sizeof (guint32));
  memset (mpeg2subt->subtitle_index, 0, sizeof (mpeg2subt->subtitle_index));
  memset (mpeg2subt->menu_index, 0, sizeof (mpeg2subt->menu_index));
  memset (mpeg2subt->subtitle_alpha, 0, sizeof (mpeg2subt->subtitle_alpha));
  memset (mpeg2subt->menu_alpha, 0, sizeof (mpeg2subt->menu_alpha));
  memset (mpeg2subt->out_buffers, 0, sizeof (mpeg2subt->out_buffers));

  gst_segment_init (&(mpeg2subt->video_segment), GST_FORMAT_TIME);
  gst_segment_init (&(mpeg2subt->subtitle_segment), GST_FORMAT_TIME);
}

static void
gst_mpeg2subt_finalize (GObject * gobject)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gobject);
  gint i;

  g_mutex_free (mpeg2subt->lock);

  g_cond_free (mpeg2subt->data_received);
  g_cond_free (mpeg2subt->data_processed);

  for (i = 0; i < 3; i++) {
    if (mpeg2subt->out_buffers[i])
      g_free (mpeg2subt->out_buffers[i]);
  }
  if (mpeg2subt->partialbuf) {
    gst_buffer_unref (mpeg2subt->partialbuf);
  }
  while (!g_queue_is_empty (mpeg2subt->subt_queue)) {
    gst_mini_object_unref (GST_MINI_OBJECT (g_queue_pop_head
			       (mpeg2subt->subt_queue)));
  }
  g_queue_free (mpeg2subt->subt_queue);
  if (mpeg2subt->last_frame) {
    gst_buffer_unref (mpeg2subt->last_frame);
  }
}

static GstCaps *
gst_mpeg2subt_getcaps (GstPad * pad)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  GstCaps *res;
  GstPad *otherpad;
  GstCaps *caps;

  otherpad =
      (pad == mpeg2subt->srcpad) ? mpeg2subt->videopad : mpeg2subt->srcpad;

  caps = gst_pad_peer_get_caps (otherpad);
  if (caps) {
    GstCaps *temp;
    const GstCaps *templ;

    /* Filter the peer caps through our own pad template. */
    templ = gst_pad_get_pad_template_caps (otherpad);
    temp = gst_caps_intersect (caps, templ);
    gst_caps_unref (caps);
    res =  temp;
  } else {
    res = gst_caps_copy (gst_pad_get_pad_template_caps (pad));
  }

  gst_object_unref (GST_OBJECT (mpeg2subt));
  return res;
}

static gboolean
gst_mpeg2subt_setcaps (GstPad * pad, GstCaps * caps)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  gboolean res =  TRUE;
  GstPad *otherpad;
  GstStructure *structure;
  gint width, height;
  gint i;

  otherpad =
      (pad == mpeg2subt->srcpad) ? mpeg2subt->videopad : mpeg2subt->srcpad;

  if (!gst_pad_set_caps (otherpad, caps)) {
    res = FALSE;
    goto done;
  }

  structure = gst_caps_get_structure (caps, 0);

  if (!gst_structure_get_int (structure, "width", &width) ||
      !gst_structure_get_int (structure, "height", &height)) {
    res = FALSE;
    goto done;
  }

  mpeg2subt->in_width = width;
  mpeg2subt->in_height = height;

  /* Allocate compositing buffers */
  for (i = 0; i < 3; i++) {
    if (mpeg2subt->out_buffers[i])
      g_free (mpeg2subt->out_buffers[i]);
    mpeg2subt->out_buffers[i] = g_malloc (sizeof (guint16) * width);
  }

  /* Retrieve the frame rate, if available. */
  if (!gst_structure_get_fraction (structure, "framerate",
	  &(mpeg2subt->frame_numerator), &(mpeg2subt->frame_denominator))) {
    /* Choose an arbitrary frame rate and hope for the best... */
    mpeg2subt->frame_numerator = 25;
    mpeg2subt->frame_denominator = 1;
  }

 done:
  gst_object_unref (GST_OBJECT (mpeg2subt));
  return res;
}

static gboolean
gst_mpeg2subt_src_activate_push (GstPad * pad, gboolean active)
{
  gboolean result = FALSE;
  GstMpeg2Subt *mpeg2subt;

  mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));

  if (active) {
    GST_MPEG2SUBT_LOCK (mpeg2subt);

    if (gst_pad_is_linked (pad)) {
      result = gst_pad_start_task (pad,
	  (GstTaskFunction) gst_mpeg2subt_loop, mpeg2subt);
    } else {
      GST_DEBUG_OBJECT (mpeg2subt, "not starting task: pad not linked");
      result = TRUE;
    }
    GST_MPEG2SUBT_UNLOCK (mpeg2subt);
  } else {
    result = gst_pad_stop_task (pad);
  }

  gst_object_unref (mpeg2subt);
  return result;
}

static gboolean
gst_mpeg2subt_event_video (GstPad *pad, GstEvent *event)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  gboolean res = TRUE;

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_FLUSH_START:
      res = gst_pad_push_event (mpeg2subt->srcpad, event);

      GST_MPEG2SUBT_LOCK (mpeg2subt);

      mpeg2subt->flushing = TRUE;

      if (mpeg2subt->last_frame != NULL) {
	gst_buffer_unref (mpeg2subt->last_frame);
	mpeg2subt->last_frame = NULL;
      }

      /* Unblock the chain and loop functions. */
      g_cond_signal (mpeg2subt->data_received);
      g_cond_signal (mpeg2subt->data_processed);

      GST_MPEG2SUBT_UNLOCK (mpeg2subt);

      /* Pause the task. */
      gst_pad_pause_task (mpeg2subt->srcpad);
      goto done;
    case GST_EVENT_FLUSH_STOP:
      res = gst_pad_push_event (mpeg2subt->srcpad, event);

      GST_MPEG2SUBT_LOCK (mpeg2subt);

      if (mpeg2subt->data != NULL) {
	gst_mini_object_unref (mpeg2subt->data);
	mpeg2subt->data = NULL;
      }
      mpeg2subt->still = FALSE;
      mpeg2subt->still_ts = GST_CLOCK_TIME_NONE;
      mpeg2subt->still_stop = GST_CLOCK_TIME_NONE;
      g_cond_signal (mpeg2subt->data_processed);

      mpeg2subt->flushing = FALSE;

      if (gst_pad_is_linked (mpeg2subt->srcpad)) {
	gst_pad_start_task (mpeg2subt->srcpad,
	    (GstTaskFunction) gst_mpeg2subt_loop, mpeg2subt);
      }

      gst_segment_init (&(mpeg2subt->video_segment), GST_FORMAT_TIME);

      GST_MPEG2SUBT_UNLOCK (mpeg2subt);
      goto done;
    case GST_EVENT_CUSTOM_DOWNSTREAM_OOB:
      GST_MPEG2SUBT_LOCK (mpeg2subt);
      if (!gst_mpeg2subt_handle_dvd_event (mpeg2subt, event, FALSE)) {
	return FALSE;
      }
      GST_MPEG2SUBT_UNLOCK (mpeg2subt);
      res = gst_pad_push_event (mpeg2subt->srcpad, event);
      goto done;
    default:
      break;
  }

  if (!GST_EVENT_IS_SERIALIZED (event)) {
    /* Forward event immediatly. */
    res = gst_pad_push_event (mpeg2subt->srcpad, event);
    goto done;
  }

  GST_MPEG2SUBT_LOCK (mpeg2subt);

  while (!mpeg2subt->flushing && mpeg2subt->data != NULL) {
    GST_MPEG2SUBT_COND_WAIT (mpeg2subt, mpeg2subt->data_processed);
  }
  if (mpeg2subt->flushing) {
    res = FALSE;
    GST_MPEG2SUBT_UNLOCK (mpeg2subt);
    goto done;
  }

  mpeg2subt->data = GST_MINI_OBJECT (event);
  g_cond_signal (mpeg2subt->data_received);

  GST_MPEG2SUBT_UNLOCK (mpeg2subt);

 done:
  gst_object_unref (GST_OBJECT (mpeg2subt));
  return res;
}

static GstFlowReturn
gst_mpeg2subt_chain_video (GstPad * pad, GstBuffer * buffer)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  GstFlowReturn res = GST_FLOW_OK;

  GST_MPEG2SUBT_LOCK (mpeg2subt);

  while (!mpeg2subt->flushing && mpeg2subt->data != NULL) {
    GST_MPEG2SUBT_COND_WAIT (mpeg2subt, mpeg2subt->data_processed);
  }
  if (mpeg2subt->flushing) {
    res = GST_FLOW_OK;
    goto done;
  }

  mpeg2subt->data = GST_MINI_OBJECT (buffer);
  g_cond_signal (mpeg2subt->data_received);

 done:
  gst_object_unref (GST_OBJECT (mpeg2subt));
  GST_MPEG2SUBT_UNLOCK (mpeg2subt);
  return res;
}

/* Check the current video frame timestamp for unexpected changes. If
   a serious gap was found and still seems fixable, returns an
   adjusted timestamp. Otherwise, returns the timestamp unmodified. */
static GstClockTime
gst_mpeg2subt_check_video_timestamp (GstMpeg2Subt * mpeg2subt,
    GstClockTime ts)
{
  if (!GST_CLOCK_TIME_IS_VALID (mpeg2subt->last_video_ts)) {
    GST_WARNING_OBJECT (mpeg2subt,
	"check video timestamp without previous newsegment");

    /* Let the buffer play normally anyway. */
    goto no_adjust;
  }

  if (ts > mpeg2subt->last_video_ts) {
    if (ts - mpeg2subt->last_video_ts > 0.2 * GST_SECOND) {
      /* We have a positive gap (wait) of more than 0.2 seconds. */
      GST_WARNING_OBJECT (mpeg2subt,
	  "timestamp gap: %0.3fs, prev: %0.3fs, actual: %0.3fs",
	  1.0 * (ts - mpeg2subt->last_video_ts) / GST_SECOND,
	  1.0 * mpeg2subt->last_video_ts / GST_SECOND,
	  1.0 * ts / GST_SECOND);

      if (mpeg2subt->adjusted_count <= MAX_ADJUST) {
	mpeg2subt->last_video_ts += (GST_SECOND * mpeg2subt->frame_denominator)
	  / mpeg2subt->frame_numerator;
	mpeg2subt->adjusted_count++;
	return mpeg2subt->last_video_ts;
      } else {
	/* Give up trying to adjust timestamps: */
	goto no_adjust;
      }
    }
  }

 no_adjust:
  mpeg2subt->last_video_ts = ts;
  mpeg2subt->adjusted_count = 0;
  return ts;
}

static void
gst_mpeg2subt_loop (GstMpeg2Subt * mpeg2subt)
{
  gboolean res;
  GstBuffer *out_buf;

  GST_MPEG2SUBT_LOCK (mpeg2subt);

  if (mpeg2subt->flushing) {
    gst_pad_pause_task (mpeg2subt->srcpad);
    goto done;
  }

  if (mpeg2subt->still && mpeg2subt->last_frame != NULL) {
    /* We are playing a still frame. */

    if (!GST_CLOCK_TIME_IS_VALID (mpeg2subt->still_ts)) {
      /* Start repeating from last frame's timestamp, regardless of
	 the event's start time. Sometimes there's a gap between them. */
      mpeg2subt->still_ts = GST_BUFFER_TIMESTAMP (mpeg2subt->last_frame);
    }

    /* Advance the timestamp. */
    mpeg2subt->still_ts += (GST_SECOND * mpeg2subt->frame_denominator) /
      mpeg2subt->frame_numerator;

    if (mpeg2subt->flushing ||
	(GST_CLOCK_TIME_IS_VALID (mpeg2subt->still_stop) &&
	    mpeg2subt->still_ts >= mpeg2subt->still_stop)) {
      /* We reached the end of the still frame. */
      mpeg2subt->still = FALSE;
      mpeg2subt->still_ts = GST_CLOCK_TIME_NONE;
      mpeg2subt->still_stop = GST_CLOCK_TIME_NONE;
      if (mpeg2subt->flushing) {
	gst_pad_pause_task (mpeg2subt->srcpad);
      }
      goto done;
    }

    /* Make a copy of the last buffer. */
    out_buf = gst_buffer_copy (mpeg2subt->last_frame);
    GST_BUFFER_TIMESTAMP (out_buf) = mpeg2subt->still_ts;

    /* Update the subtitle state and blend it if necessary. */
    gst_mpeg2subt_update (mpeg2subt, mpeg2subt->still_ts);
    if (mpeg2subt->forced_display) {
      gst_mpeg2subt_merge_title (mpeg2subt, out_buf);
    }

    GST_LOG_OBJECT (mpeg2subt,
	"pushing still update frame with timestamp %" GST_TIME_FORMAT,
	GST_TIME_ARGS (mpeg2subt->still_ts));

    GST_MPEG2SUBT_UNLOCK (mpeg2subt);
    res = gst_pad_push (mpeg2subt->srcpad, out_buf);
    GST_MPEG2SUBT_LOCK (mpeg2subt);

    goto done;
  }

  /* Wait for data to become available. */
  while (!mpeg2subt->flushing && mpeg2subt->data == NULL) {
    GST_MPEG2SUBT_COND_WAIT (mpeg2subt, mpeg2subt->data_received);
  }
  if (mpeg2subt->flushing) {
    gst_pad_pause_task (mpeg2subt->srcpad);
    goto done;
  }

  if (GST_IS_BUFFER (mpeg2subt->data)) {
    GstBuffer *buffer = GST_BUFFER(mpeg2subt->data);

    if (mpeg2subt->last_frame) {
      gst_buffer_unref (mpeg2subt->last_frame);
    }
    out_buf = mpeg2subt->last_frame = gst_buffer_ref (buffer);

    gst_mpeg2subt_update (mpeg2subt, GST_BUFFER_TIMESTAMP (out_buf));

    if ((!mpeg2subt->hide && mpeg2subt->display) ||
	mpeg2subt->forced_display) {
      /* Merge the current subtitle. */
      out_buf = gst_buffer_make_writable (out_buf);
      gst_mpeg2subt_merge_title (mpeg2subt, out_buf);
    }

    GST_LOG_OBJECT (mpeg2subt, "Pushing frame with timestamp %"
	GST_TIME_FORMAT, GST_TIME_ARGS (GST_BUFFER_TIMESTAMP (out_buf)));

    /* Adjust the frame's timestamp. */
    GST_BUFFER_TIMESTAMP (out_buf) =
      gst_mpeg2subt_check_video_timestamp (mpeg2subt,
	  GST_BUFFER_TIMESTAMP (out_buf));

    /* Push the buffer. */
    GST_MPEG2SUBT_UNLOCK (mpeg2subt);
    res = gst_pad_push (mpeg2subt->srcpad, out_buf);
    GST_MPEG2SUBT_LOCK (mpeg2subt);
  } else if (GST_IS_EVENT (mpeg2subt->data)) {
    GstEvent *event = GST_EVENT(mpeg2subt->data);

    switch (GST_EVENT_TYPE (event)) {
      case GST_EVENT_NEWSEGMENT:
      {
	gboolean update;
	gdouble rate;
	GstFormat format;
	gint64 start;
	gint64 stop;
	gint64 position;

	gst_event_parse_new_segment (event, &update, &rate, &format,
	    &start, &stop, &position);

	gst_segment_set_newsegment (&(mpeg2subt->video_segment), update,
	    rate, format, start, stop, position);

	mpeg2subt->last_video_ts = start;
	break;
      }
      case GST_EVENT_EOS:
	/* Stop the task. */
	gst_pad_pause_task (mpeg2subt->srcpad);
	break;
      case GST_EVENT_CUSTOM_DOWNSTREAM:
	if (!gst_mpeg2subt_handle_dvd_event (mpeg2subt, event, FALSE)) {
	  return;
	}
	break;
      default:
	break;
    }

    GST_MPEG2SUBT_UNLOCK (mpeg2subt);
    res = gst_pad_push_event (mpeg2subt->srcpad, event);
    GST_MPEG2SUBT_LOCK (mpeg2subt);
  } else {
    g_return_if_fail (FALSE);
  }

  /* Make room for the next data item. */ 
  mpeg2subt->data = NULL;
  g_cond_signal (mpeg2subt->data_processed);

 done:
  GST_MPEG2SUBT_UNLOCK (mpeg2subt);
}

static gboolean
gst_mpeg2subt_src_event (GstPad * pad, GstEvent * event)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  gboolean res = TRUE;

  res = gst_pad_send_event (GST_PAD_PEER (mpeg2subt->videopad), event);

  gst_object_unref (GST_OBJECT (mpeg2subt));
  return res;  
}

/* Execute the current command block. */
static void
gst_mpeg2subt_execute_block (GstMpeg2Subt * mpeg2subt)
{
  guchar *start;
  guchar *end;
  guchar *cur_cmd;
  gboolean broken = FALSE;

#define PARSE_BYTES_NEEDED(x) \
  if ((cur_cmd + (x)) >= end) { \
    GST_WARNING("Subtitle stream broken parsing %d", *cur_cmd); \
    broken = TRUE; \
    break; \
  }

  start = GST_BUFFER_DATA (mpeg2subt->cur_cmds_buf);
  end = start + GST_READ_UINT16_BE (start);

  mpeg2subt->forced_display = FALSE;

  cur_cmd = mpeg2subt->cur_cmds + 4;

  while (cur_cmd < end && !broken) {
    switch (*cur_cmd) {
      case SPU_FORCE_DISPLAY:  /* Forced display menu subtitle. */
        mpeg2subt->forced_display = TRUE;
        cur_cmd++;
        break;
      case SPU_SHOW:           /* Show the current subpicture. */
	mpeg2subt->display = TRUE;
        cur_cmd++;
        break;
      case SPU_HIDE:           /* Hide the current subpicture. */
        mpeg2subt->display = FALSE;
        cur_cmd++;
        break;
      case SPU_SET_PALETTE:    /* Set the standard palette. */
        PARSE_BYTES_NEEDED (3);

        mpeg2subt->subtitle_index[3] = cur_cmd[1] >> 4;
        mpeg2subt->subtitle_index[2] = cur_cmd[1] & 0xf;
        mpeg2subt->subtitle_index[1] = cur_cmd[2] >> 4;
        mpeg2subt->subtitle_index[0] = cur_cmd[2] & 0xf;
	gst_mpeg2subt_setup_palette (mpeg2subt);
        cur_cmd += 3;
        break;
      case SPU_SET_ALPHA:      /* Set the transparency palette. */
        PARSE_BYTES_NEEDED (3);

        mpeg2subt->subtitle_alpha[3] = cur_cmd[1] >> 4;
        mpeg2subt->subtitle_alpha[2] = cur_cmd[1] & 0xf;
        mpeg2subt->subtitle_alpha[1] = cur_cmd[2] >> 4;
        mpeg2subt->subtitle_alpha[0] = cur_cmd[2] & 0xf;
	gst_mpeg2subt_setup_palette (mpeg2subt);
        cur_cmd += 3;
        break;
      case SPU_SET_SIZE:       /* Set the image coordinates. */
        PARSE_BYTES_NEEDED (7);

        mpeg2subt->left =
            CLAMP ((((unsigned int) cur_cmd[1]) << 4) | (cur_cmd[2] >> 4), 0,
            (mpeg2subt->in_width - 1));
        mpeg2subt->top =
            CLAMP ((((unsigned int) cur_cmd[4]) << 4) | (cur_cmd[5] >> 4), 0,
            (mpeg2subt->in_height - 1));
        mpeg2subt->right =
            CLAMP ((((cur_cmd[2] & 0x0f) << 8) | cur_cmd[3]), 0,
            (mpeg2subt->in_width - 1));
        mpeg2subt->bottom =
            CLAMP ((((cur_cmd[5] & 0x0f) << 8) | cur_cmd[6]), 0,
            (mpeg2subt->in_height - 1));

        GST_DEBUG_OBJECT (mpeg2subt, "left %d, top %d, right %d, bottom %d",
			  mpeg2subt->left, mpeg2subt->top, mpeg2subt->right,
			  mpeg2subt->bottom);
        cur_cmd += 7;
        break;
      case SPU_SET_OFFSETS:    /* Set the active top and bottom field
				  image offsets. */
        PARSE_BYTES_NEEDED (5);

	/* The current buffer is referenced separately. */
	if (mpeg2subt->current_buf) {
	  gst_buffer_unref (mpeg2subt->current_buf);
	}
	mpeg2subt->current_buf = gst_buffer_ref (mpeg2subt->cur_cmds_buf);

        mpeg2subt->offset[0] = GST_READ_UINT16_BE (cur_cmd + 1);
        mpeg2subt->offset[1] = GST_READ_UINT16_BE (cur_cmd + 3);
        GST_DEBUG_OBJECT (mpeg2subt, "Offset1 %d, Offset2 %d",
			  mpeg2subt->offset[0], mpeg2subt->offset[1]);

        cur_cmd += 5;
        break;
      case SPU_WIPE:
	{
	  guint length;

	  GST_WARNING ("SPU_WIPE not yet implemented");
	  PARSE_BYTES_NEEDED (3);

	  length = (cur_cmd[1] << 8) | (cur_cmd[2]);
	  cur_cmd += 1 + length;
	}
        break;
      case SPU_END:
	return;
      default:
        GST_ERROR ("Invalid sequence in subtitle packet header"
		   " (%.2x). Skipping", *cur_cmd);
        broken = TRUE;
        break;
    }
  }
}

/* Process events from the front of the subtitle queue until a buffer
   is reached or the queue is empty. Returns the first buffer seen or
   NULL if the queue is empty. */
static GstBuffer *
gst_mpeg2subt_process_events (GstMpeg2Subt * mpeg2subt)
{
  GstMiniObject *data;
  GstEvent *event;

  data = GST_MINI_OBJECT (g_queue_peek_head ((mpeg2subt)->subt_queue));
  while (data != NULL && GST_IS_EVENT (data)) {
    event = GST_EVENT (data);

    switch (GST_EVENT_TYPE (event)) {
      case GST_EVENT_NEWSEGMENT:
      {
	gboolean update;
	gdouble rate;
	GstFormat format;
	gint64 start;
	gint64 stop;
	gint64 position;

	gst_event_parse_new_segment (event, &update, &rate, &format,
	    &start, &stop, &position);

	gst_segment_set_newsegment (&(mpeg2subt->subtitle_segment), update,
	    rate, format, start, stop, position);
	break;
      }
      case GST_EVENT_CUSTOM_DOWNSTREAM:
	GST_LOG_OBJECT (mpeg2subt,
	    "DVD event on subtitle pad with timestamp %llu",
	    GST_EVENT_TIMESTAMP (event));
	gst_mpeg2subt_handle_dvd_event (mpeg2subt, event, TRUE);
	break;
      default:
	break;
    }

    /* Discard the event. */
    g_queue_pop_head (mpeg2subt->subt_queue);
    gst_event_unref (event);
    
    data = GST_MINI_OBJECT (g_queue_peek_head ((mpeg2subt)->subt_queue));
  }

  if (data == NULL) {
    return NULL;
  } else {
    return GST_BUFFER (data);
  }
}

/* Advance the current command block pointer to the next command
   block, or to NULL when no next block is available, and update all
   related fields.

   Returns TRUE if and only if a transition actually happened. */
static gboolean
gst_mpeg2subt_next_block (GstMpeg2Subt * mpeg2subt)
{
  guchar *contents;

  if (mpeg2subt->cur_cmds == NULL) {
    /* Check for a new packet. */
    mpeg2subt->cur_cmds_buf = gst_mpeg2subt_process_events (mpeg2subt);
    if (mpeg2subt->cur_cmds_buf == NULL) {
      /* No transition. */
      return FALSE;
    }

    /* Go to the first command block. */
    contents = GST_BUFFER_DATA (mpeg2subt->cur_cmds_buf);
    mpeg2subt->cur_cmds = contents + GST_READ_UINT16_BE (contents + 2);
  } else {
    guchar *next_cmds;

    contents = GST_BUFFER_DATA (mpeg2subt->cur_cmds_buf);

    /* Determine the address of the next command block. */
    next_cmds = contents + GST_READ_UINT16_BE (mpeg2subt->cur_cmds + 2);

    /* next_cmds should still fall in the packet. */
    g_return_val_if_fail (contents < next_cmds &&
	next_cmds < contents + GST_READ_UINT16_BE (contents), FALSE);

    if (next_cmds != mpeg2subt->cur_cmds) {
      /* Just move to the next block. */
      mpeg2subt->cur_cmds = next_cmds;
    } else {
      /* We are in the last command block in this packet: */

      /* Discard the current packet... */
      gst_buffer_unref (GST_BUFFER (g_queue_pop_head
				    (mpeg2subt->subt_queue)));

      /* and check for a new one. */
      mpeg2subt->cur_cmds_buf = gst_mpeg2subt_process_events (mpeg2subt);
      if (mpeg2subt->cur_cmds_buf == NULL) {
	/* No more packets available for the time being. */
	mpeg2subt->cur_cmds = NULL;
      } else {
	/* Go to the first command block. */
	contents = GST_BUFFER_DATA (mpeg2subt->cur_cmds_buf);
	mpeg2subt->cur_cmds = contents + GST_READ_UINT16_BE (contents + 2);
      }
    }
  }

  /* Update the current block time. */
  if (mpeg2subt->cur_cmds != NULL) {
    GstClockTime ts;

    ts = GST_BUFFER_TIMESTAMP (mpeg2subt->cur_cmds_buf);
    if (ts == GST_CLOCK_TIME_NONE) {
      mpeg2subt->cur_cmds_time = GST_CLOCK_TIME_NONE;
    } else {
      mpeg2subt->cur_cmds_time = ts +
	DELAY_TO_GST(GST_READ_UINT16_BE (mpeg2subt->cur_cmds));
    }
  } else {
    mpeg2subt->cur_cmds_time = GST_CLOCK_TIME_NONE;
  }

  /* We did a transition. */
  return TRUE;
}

/* Execute all SPU commands contained in the queue, whose execution
   time is smaller than the specified time. */
static void
gst_mpeg2subt_update (GstMpeg2Subt * mpeg2subt, GstClockTime time)
{
  if (time == GST_CLOCK_TIME_NONE) {
    return;
  }

  GST_LOG_OBJECT (mpeg2subt, "updating SPU commands, time: %Ld",
      time);

  if (mpeg2subt->cur_cmds == NULL) {
    /* Try to advance once, just in case new SPU packets have arrived. */
    gst_mpeg2subt_next_block (mpeg2subt);
  }

  /* When comparing subtitle and video times, use running time based
     on the NEWSEGMENT events seen on both streams till now. */
  while (mpeg2subt->cur_cmds != NULL &&
	 (mpeg2subt->cur_cmds_time == GST_CLOCK_TIME_NONE ||
	  gst_segment_to_running_time (&(mpeg2subt->subtitle_segment),
	      GST_FORMAT_TIME, mpeg2subt->cur_cmds_time) <= 
	     gst_segment_to_running_time (&(mpeg2subt->video_segment),
		 GST_FORMAT_TIME, time) + COMPARE_GAP)) {
    gst_mpeg2subt_execute_block (mpeg2subt);
    gst_mpeg2subt_next_block (mpeg2subt);
  }
}

inline int
gst_get_nibble (guchar * buffer, RLE_state * state)
{
  if (state->aligned) {
    state->next = buffer[state->offset[state->id]++];
    state->aligned = 0;
    return state->next >> 4;
  } else {
    state->aligned = 1;
    return state->next & 0xf;
  }
}

/* Premultiply the current lookup table into the palette_cache */
static void
gst_mpeg2subt_setup_palette (GstMpeg2Subt * mpeg2subt)
{
  gint i;
  YUVA_val *target = mpeg2subt->palette_cache;

  for (i = 0; i < 4; i++, target++) {
    guint32 col = mpeg2subt->current_clut[mpeg2subt->subtitle_index[i]];

    target->Y = (guint16) ((col >> 16) & 0xff) * mpeg2subt->subtitle_alpha[i];
    target->U = (guint16) ((col >> 8) & 0xff) * mpeg2subt->subtitle_alpha[i];
    target->V = (guint16) (col & 0xff) * mpeg2subt->subtitle_alpha[i];
    target->A = mpeg2subt->subtitle_alpha[i];
  }
}

/* Premultiply the current lookup table into the highlight_palette_cache */
static void
gst_mpeg2subt_setup_highlight_palette (GstMpeg2Subt * mpeg2subt)
{
  gint i;
  YUVA_val *target = mpeg2subt->highlight_palette_cache;

  for (i = 0; i < 4; i++, target++) {
    guint32 col = mpeg2subt->current_clut[mpeg2subt->menu_index[i]];

    target->Y = (guint16) ((col >> 16) & 0xff) * mpeg2subt->menu_alpha[i];
    target->U = (guint16) ((col >> 8) & 0xff) * mpeg2subt->menu_alpha[i];
    target->V = (guint16) (col & 0xff) * mpeg2subt->menu_alpha[i];
    target->A = mpeg2subt->menu_alpha[i];
  }
}

inline guint
gst_get_rle_code (guchar * buffer, RLE_state * state)
{
  gint code;

  code = gst_get_nibble (buffer, state);
  if (code < 0x4) {             /* 4 .. f */
    code = (code << 4) | gst_get_nibble (buffer, state);
    if (code < 0x10) {          /* 1x .. 3x */
      code = (code << 4) | gst_get_nibble (buffer, state);
      if (code < 0x40) {        /* 04x .. 0fx */
        code = (code << 4) | gst_get_nibble (buffer, state);
      }
    }
  }
  return code;
}

/* 
 * This function steps over each run-length segment, drawing 
 * into the YUVA buffers as it goes. UV are composited and then output
 * at half width/height
 */
static void
gst_draw_rle_line (GstMpeg2Subt * mpeg2subt, guchar * buffer,
		   RLE_state * state)
{
  gint length, colourid;
  gint right = mpeg2subt->right + 1;
  YUVA_val *normal_colour_entry;
  YUVA_val *highlight_colour_entry;
  guint code;
  gint x, x_final;
  guchar *target_Y;
  guint16 *target_U;
  guint16 *target_V;
  guint16 *target_A;
  guint16 inv_alpha;

  target_Y = state->target_Y;
  target_U = mpeg2subt->out_buffers[0];
  target_V = mpeg2subt->out_buffers[1];
  target_A = mpeg2subt->out_buffers[2];
  x = mpeg2subt->left;
  while (x < right) {
    code = gst_get_rle_code (buffer, state);
    length = code >> 2;
    colourid = code & 3;
    normal_colour_entry = mpeg2subt->palette_cache + colourid;
    highlight_colour_entry = mpeg2subt->highlight_palette_cache + colourid;

    /* Length = 0 implies fill to the end of the line */
    if (length == 0)
      length = right - x;
    else {
      /* Restrict the colour run to the end of the line */
      length = length < (right - x) ? length : (right - x);
    }
    x_final = x + length;

    /* FIXME: There's a lot of room for optimization
       here. Particularly, you can avoid a good deal of work when
       alpha is 0. For the moment, however, I'm just striving for a
       correct behavior. M. S. */

    if (state->clip_top <= state->y && state->y <= state->clip_bottom) {
      inv_alpha = 0xf - normal_colour_entry->A;
      for (; x < state->clip_left && x < x_final; x++) {
	*target_Y = ((inv_alpha * (*target_Y)) + normal_colour_entry->Y) / 0xf;
	*target_U += normal_colour_entry->U;
	*target_V += normal_colour_entry->V;
	*target_A += normal_colour_entry->A;
	target_Y++;
	target_U++;
	target_V++;
	target_A++;
      }

      inv_alpha = 0xf - highlight_colour_entry->A;
      for (; x <= state->clip_right && x < x_final; x++) {
	*target_Y = ((inv_alpha * (*target_Y)) +
		     highlight_colour_entry->Y) / 0xf;
	*target_U += highlight_colour_entry->U;
	*target_V += highlight_colour_entry->V;
	*target_A += highlight_colour_entry->A;
	target_Y++;
	target_U++;
	target_V++;
	target_A++;
      }
    }

    inv_alpha = 0xf - normal_colour_entry->A;
    for (; x < x_final; x++) {
      *target_Y = ((inv_alpha * (*target_Y)) + normal_colour_entry->Y) / 0xf;
      *target_U += normal_colour_entry->U;
      *target_V += normal_colour_entry->V;
      *target_A += normal_colour_entry->A;
      target_Y++;
      target_U++;
      target_V++;
      target_A++;
    }
  }
}

inline void
gst_merge_uv_data (GstMpeg2Subt * mpeg2subt, guchar * buffer,
		   RLE_state * state)
{
  gint x;
  guchar *target_V;
  guchar *target_U;
  gint width = mpeg2subt->right - mpeg2subt->left + 1;

  guint16 *comp_U;
  guint16 *comp_V;
  guint16 *comp_A;

  /* The compositing buffers should contain the results of
   * accumulating 2 scanlines of U, V (premultiplied) and A
   * data. Merge them back into their output buffers at half
   * width/height.
   */
  target_U = state->target_U;
  target_V = state->target_V;
  comp_U = mpeg2subt->out_buffers[0];
  comp_V = mpeg2subt->out_buffers[1];
  comp_A = mpeg2subt->out_buffers[2];

  for (x = 0; x < width; x += 2) {
    guint16 temp1, temp2;

    /* Average out the alpha accumulated to compute transparency */
    guint16 alpha = (comp_A[0] + comp_A[1]);

    if (alpha > 0) {
      temp1 = (*target_U) * ((4 * 0xf) - alpha) + comp_U[0] + comp_U[1];
      temp2 = (*target_V) * ((4 * 0xf) - alpha) + comp_V[0] + comp_V[1];
      *target_U = temp1 / (4 * 0xf);
      *target_V = temp2 / (4 * 0xf);
    };
    comp_U += 2;
    comp_V += 2;
    comp_A += 2;
    target_U++;
    target_V++;
  }
}

/*
 * Decode the RLE subtitle image and blend with the current
 * frame buffer.
 */
static void
gst_mpeg2subt_merge_title (GstMpeg2Subt * mpeg2subt, GstBuffer * buf)
{
  gint Y_stride;
  gint UV_stride;

  guchar *buffer;
  guint16 data_size;
  RLE_state state;

  if (!mpeg2subt->current_buf) {
    return;
  }

  buffer = GST_BUFFER_DATA (mpeg2subt->current_buf);
  data_size = GST_READ_UINT16_BE (buffer);

  /* Set up the initial offsets, remembering the half-res size for UV
   * in I420 packing see http://www.fourcc.org for details
   */
  Y_stride = mpeg2subt->in_width;
  UV_stride = (mpeg2subt->in_width + 1) / 2;

  GST_LOG_OBJECT (mpeg2subt,
      "Merging subtitle on frame at time %" G_GUINT64_FORMAT
      " using %s colour table", GST_BUFFER_TIMESTAMP (buf),
      mpeg2subt->forced_display ? "menu" : "subtitle");

  state.id = 0;
  state.aligned = 1;
  state.offset[0] = mpeg2subt->offset[0];
  state.offset[1] = mpeg2subt->offset[1];
  state.next = 0;

  /* Determine the highlight region. */
  if (mpeg2subt->forced_display) {
    state.clip_right = mpeg2subt->clip_right;
    state.clip_left = mpeg2subt->clip_left;
    state.clip_bottom = mpeg2subt->clip_bottom;
    state.clip_top = mpeg2subt->clip_top;
  } else {
    state.clip_right = -1;
    state.clip_left = -1;
    state.clip_bottom = -1;
    state.clip_top = -1;
  }

  state.y = mpeg2subt->top;

  state.target_Y = GST_BUFFER_DATA (buf) + mpeg2subt->left +
    (state.y * Y_stride);
  state.target_V = GST_BUFFER_DATA (buf) + (Y_stride * mpeg2subt->in_height)
      + ((mpeg2subt->left) / 2) + ((state.y / 2) * UV_stride);
  state.target_U =
      state.target_V + UV_stride * ((mpeg2subt->in_height + 1) / 2);

  memset (mpeg2subt->out_buffers[0], 0, sizeof (guint16) * Y_stride);
  memset (mpeg2subt->out_buffers[1], 0, sizeof (guint16) * Y_stride);
  memset (mpeg2subt->out_buffers[2], 0, sizeof (guint16) * Y_stride);

  /* Now draw scanlines until we hit state.clip_bottom or end of RLE data */
  for (; ((state.offset[1] < data_size + 2) &&
	  (state.y <= mpeg2subt->bottom)); state.y++) {
    gst_draw_rle_line (mpeg2subt, buffer, &state);
    if (state.id) {
      gst_merge_uv_data (mpeg2subt, buffer, &state);

      /* Clear the compositing buffers */
      memset (mpeg2subt->out_buffers[0], 0, sizeof (guint16) * Y_stride);
      memset (mpeg2subt->out_buffers[1], 0, sizeof (guint16) * Y_stride);
      memset (mpeg2subt->out_buffers[2], 0, sizeof (guint16) * Y_stride);

      state.target_U += UV_stride;
      state.target_V += UV_stride;
    }
    state.target_Y += Y_stride;

    /* Realign the RLE state for the next line */
    if (!state.aligned)
      gst_get_nibble (buffer, &state);
    state.id = !state.id;
  }
}

static GstFlowReturn
gst_mpeg2subt_chain_subtitle (GstPad * pad, GstBuffer * buffer)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  guint16 packet_size;
  guchar *data;
  glong size = 0;

  GST_MPEG2SUBT_LOCK (mpeg2subt);

  /* deal with partial frame from previous buffer */
  if (mpeg2subt->partialbuf) {
    GstBuffer *merge;

    merge = gst_buffer_merge (mpeg2subt->partialbuf, buffer);
    gst_buffer_unref (mpeg2subt->partialbuf);
    gst_buffer_unref (buffer);
    mpeg2subt->partialbuf = merge;
  } else {
    mpeg2subt->partialbuf = buffer;
  }

  data = GST_BUFFER_DATA (mpeg2subt->partialbuf);
  size = GST_BUFFER_SIZE (mpeg2subt->partialbuf);

  if (size > 4) {
    packet_size = GST_READ_UINT16_BE (data);

    if (packet_size == size) {
      if (GST_BUFFER_TIMESTAMP (mpeg2subt->partialbuf) !=
	  GST_CLOCK_TIME_NONE) {
	GST_DEBUG_OBJECT (mpeg2subt,
	    "Got subtitle buffer, pts " GST_TIME_FORMAT,
	    GST_TIME_ARGS (GST_BUFFER_TIMESTAMP
		(mpeg2subt->partialbuf)));
      } else {
	GST_DEBUG_OBJECT (mpeg2subt, "Got subtitle buffer, no pts");
      }
      GST_LOG_OBJECT (mpeg2subt, "Subtitle packet size %d, current size %ld",
	  packet_size, size);

      g_queue_push_tail (mpeg2subt->subt_queue, mpeg2subt->partialbuf);

      mpeg2subt->partialbuf = NULL;
    }
  }

  gst_object_unref (GST_OBJECT (mpeg2subt));
  GST_MPEG2SUBT_UNLOCK (mpeg2subt);
  return GST_FLOW_OK;
}

static gboolean
gst_mpeg2subt_event_subtitle (GstPad *pad, GstEvent *event)
{
  GstMpeg2Subt *mpeg2subt = GST_MPEG2SUBT (gst_pad_get_parent (pad));
  gboolean res = TRUE;

  GST_MPEG2SUBT_LOCK (mpeg2subt);

  /* This function doesn't forward any events to the source pad. The
     video event function does that. */

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_FLUSH_STOP:
      if (mpeg2subt->partialbuf) {
	gst_buffer_unref (mpeg2subt->partialbuf);
	mpeg2subt->partialbuf = NULL;
      }

      while (!g_queue_is_empty (mpeg2subt->subt_queue)) {
	gst_mini_object_unref (GST_MINI_OBJECT (g_queue_pop_head
				   (mpeg2subt->subt_queue)));
      }

      gst_mpeg2subt_reset_highlight (mpeg2subt);
      gst_segment_init (&(mpeg2subt->subtitle_segment), GST_FORMAT_TIME);
      gst_event_unref (event);
      break;
    case GST_EVENT_CUSTOM_DOWNSTREAM_OOB:
      GST_LOG_OBJECT (mpeg2subt,
	  "out-of-band DVD event on subtitle pad with timestamp %llu",
	  GST_EVENT_TIMESTAMP (event));
      res = gst_mpeg2subt_handle_dvd_event (mpeg2subt, event, TRUE);
      gst_event_unref (event);
      break;
    default:
      if (GST_EVENT_IS_SERIALIZED (event)) {
	/* Put the event in the queue, to make sure it is processed in
	   the right sequence with respect to subtitle buffers. */
	g_queue_push_tail (mpeg2subt->subt_queue, event);
      }  
      break;
  }

  gst_object_unref (GST_OBJECT (mpeg2subt));
  GST_MPEG2SUBT_UNLOCK (mpeg2subt);
  return res;
}

static void
gst_mpeg2subt_reset_highlight (GstMpeg2Subt * mpeg2subt)
{
  GST_DEBUG_OBJECT (mpeg2subt, "Resetting highlight");

  mpeg2subt->cur_cmds = NULL;
  mpeg2subt->cur_cmds_buf = NULL;
  mpeg2subt->cur_cmds_time = GST_CLOCK_TIME_NONE;

  if (mpeg2subt->current_buf) {
    gst_buffer_unref (mpeg2subt->current_buf);
    mpeg2subt->current_buf = NULL;
  }
  mpeg2subt->display = FALSE;
  mpeg2subt->forced_display = FALSE;

  /* Reset everything except for the CLUT, which is generally still
     valid after seeking. */
  memset (mpeg2subt->subtitle_index, 0, sizeof (mpeg2subt->subtitle_index));
  memset (mpeg2subt->menu_index, 0, sizeof (mpeg2subt->menu_index));
  memset (mpeg2subt->subtitle_alpha, 0, sizeof (mpeg2subt->subtitle_alpha));
  memset (mpeg2subt->menu_alpha, 0, sizeof (mpeg2subt->menu_alpha));
}

static gboolean
gst_mpeg2subt_handle_dvd_event (GstMpeg2Subt * mpeg2subt, GstEvent * event,
    gboolean from_sub_pad)
{
  gboolean res = TRUE;
  const GstStructure *structure;
  const gchar *event_type;

  structure = gst_event_get_structure (event);

  if (!gst_structure_has_name (structure, "application/x-gst-dvd")) {
    /* This isn't a DVD event. */
    return gst_pad_push_event (mpeg2subt->srcpad, event);
  }

  event_type = gst_structure_get_string (structure, "event");
  g_return_val_if_fail (event_type != NULL, FALSE);

  if (from_sub_pad && !strcmp (event_type, "dvd-spu-highlight")) {
    gint button;
    guint palette;
    gint sx, sy, ex, ey;
    gint i;

    /* Details for the highlight region to display */
    if (!gst_structure_get_int (structure, "button", &button) ||
        !gst_structure_has_field_typed (structure, "palette", G_TYPE_UINT) ||
        !gst_structure_get_int (structure, "sx", &sx) ||
        !gst_structure_get_int (structure, "sy", &sy) ||
        !gst_structure_get_int (structure, "ex", &ex) ||
        !gst_structure_get_int (structure, "ey", &ey)) {
      GST_ERROR ("Invalid dvd-spu-highlight event received");
      res = FALSE;
      goto done;
    }

    palette = g_value_get_uint (gst_structure_get_value (structure,
				                         "palette"));

    mpeg2subt->current_button = button;
    mpeg2subt->clip_left = sx;
    mpeg2subt->clip_top = sy;
    mpeg2subt->clip_right = ex;
    mpeg2subt->clip_bottom = ey;
    for (i = 0; i < 4; i++) {
      mpeg2subt->menu_alpha[i] = ((guint32) (palette) >> (i * 4)) & 0x0f;
      mpeg2subt->menu_index[i] =
	((guint32) (palette) >> (16 + (i * 4))) & 0x0f;
    }
    gst_mpeg2subt_setup_highlight_palette (mpeg2subt);

    GST_DEBUG_OBJECT (mpeg2subt,
		      "New button activated clip=(%d,%d) to "
		      "(%d,%d) palette 0x%x", sx, sy, ex, ey, palette);
  } else if (from_sub_pad && !strcmp (event_type, "dvd-spu-clut-change")) {
    /* Take a copy of the colour table */
    gchar name[16];
    int i;
    gint value;

    GST_LOG_OBJECT (mpeg2subt, "New colour table received");
    for (i = 0; i < 16; i++) {
      sprintf (name, "clut%02d", i);
      if (!gst_structure_get_int (structure, name, &value)) {
        GST_ERROR ("dvd-spu-clut-change event did not contain %s field", name);
	res = FALSE;
        goto done;
      }
      mpeg2subt->current_clut[i] = (guint32) (value);
    }
  } else if (from_sub_pad && !strcmp (event_type, "dvd-spu-reset-highlight")) {
    /* Turn off forced highlight display */
    mpeg2subt->current_button = 0;
    mpeg2subt->clip_left = 0;
    mpeg2subt->clip_top = 0;
    mpeg2subt->clip_right = 0;
    mpeg2subt->clip_bottom = 0;
    gst_mpeg2subt_reset_highlight (mpeg2subt);
    GST_LOG_OBJECT (mpeg2subt, "Clearing button state");
  } else if (from_sub_pad && !strcmp (event_type, "dvd-spu-hide")) {
    mpeg2subt->hide = TRUE;
  } else if (from_sub_pad && !strcmp (event_type, "dvd-spu-show")) {
    mpeg2subt->hide = FALSE;
  } else if (!from_sub_pad && !strcmp (event_type, "dvd-spu-still-frame")) {
    /* Display a still frame. */
    GstClockTime start, stop;

    /* Parse the still frame event. */
    if (!gst_structure_get_clock_time (structure, "start",
	    &start) ||
	!gst_structure_get_clock_time (structure, "stop",
	    &stop)) {
      GST_ERROR_OBJECT (mpeg2subt, "incorrect dvd-spu-still-frame event");
      res = FALSE;
      goto done;
    }
    
    GST_DEBUG_OBJECT (mpeg2subt, "received still frame notification, start: %"
	GST_TIME_FORMAT ", stop: %" GST_TIME_FORMAT, GST_TIME_ARGS (start),
	GST_TIME_ARGS (stop));

    mpeg2subt->still = TRUE;
    mpeg2subt->still_stop = stop;
    /* The loop function initializes still_ts. */
  } else if (!from_sub_pad && !strcmp (event_type, "dvd-spu-nav-sequence")) {
    gint number;
    GstStructure *msg_str;

    if (!gst_structure_get_int (structure, "number", &number)) {
      GST_ERROR_OBJECT (mpeg2subt,
	  "dvd-spu-nav-sequence event did not contain field 'number'");
      res = FALSE;
      goto done;
    }

    msg_str = gst_structure_new ("mpeg2subt.nav_sequence",
	"number", G_TYPE_INT, number, NULL);
    gst_element_post_message (GST_ELEMENT (mpeg2subt),
	gst_message_new_custom (GST_MESSAGE_ELEMENT,
	    GST_OBJECT (mpeg2subt), msg_str));
  } else {
    /* Ignore all other unknown events */
    /*GST_LOG_OBJECT (mpeg2subt, "Ignoring DVD event %s from %s pad",
      event_type, from_sub_pad ? "sub" : "video");*/
  }

 done:
  return res;
}

static void
gst_mpeg2subt_set_property (GObject * object, guint prop_id,
    const GValue * value, GParamSpec * pspec)
{
  GstMpeg2Subt *src;

  /* it's not null if we got it, but it might not be ours */
  g_return_if_fail (GST_IS_MPEG2SUBT (object));
  src = GST_MPEG2SUBT (object);

  switch (prop_id) {
    default:
      break;
  }
}

static void
gst_mpeg2subt_get_property (GObject * object, guint prop_id, GValue * value,
    GParamSpec * pspec)
{
  GstMpeg2Subt *src;

  /* it's not null if we got it, but it might not be ours */
  g_return_if_fail (GST_IS_MPEG2SUBT (object));
  src = GST_MPEG2SUBT (object);

  switch (prop_id) {
    default:
      break;
  }
}

static gboolean
plugin_init (GstPlugin * plugin)
{
  return gst_element_register (plugin, "mpeg2subt",
      GST_RANK_NONE, GST_TYPE_MPEG2SUBT);
}

GST_PLUGIN_DEFINE (GST_VERSION_MAJOR,
    GST_VERSION_MINOR,
    "mpeg2sub",
    "MPEG-2 video subtitle parser",
    plugin_init, VERSION, "LGPL",
    PACKAGE " (temporary fork from gst-plugins)",
    ORIGIN)
