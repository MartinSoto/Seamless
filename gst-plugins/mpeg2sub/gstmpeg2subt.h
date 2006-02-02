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


#ifndef __GST_MPEG2SUBT_H__
#define __GST_MPEG2SUBT_H__


#include <gst/gst.h>


#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */


#define GST_TYPE_MPEG2SUBT \
  (gst_mpeg2subt_get_type())
#define GST_MPEG2SUBT(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_MPEG2SUBT,GstMpeg2Subt))
#define GST_MPEG2SUBT_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_MPEG2SUBT,GstMpeg2Subt))
#define GST_IS_MPEG2SUBT(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_MPEG2SUBT))
#define GST_IS_MPEG2SUBT_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_MPEG2SUBT))

/* Lock and unlock the object, and wait for conditions. */
#ifdef GST_MPEG2SUBT_DEBUG_LOCKING

#define GST_MPEG2SUBT_LOCK(mpeg2subt) \
  {g_mutex_lock ((mpeg2subt)->lock); \
   fprintf (stderr, "+++ Locking in '%s', line %d\n", __func__, __LINE__);}
#define GST_MPEG2SUBT_UNLOCK(mpeg2subt) \
  {fprintf (stderr, "+++ Unlocking in '%s', line %d\n", __func__, __LINE__); \
   g_mutex_unlock ((mpeg2subt)->lock);}
#define GST_MPEG2SUBT_COND_WAIT(mpeg2subt, cond) \
  {fprintf (stderr, "+++ Unlocking (wait) in '%s', line %d\n", __func__, __LINE__); \
   g_cond_wait (cond, (mpeg2subt)->lock); \
   fprintf (stderr, "+++ Locking (wait) in '%s', line %d\n", __func__, __LINE__);}

#else

#define GST_MPEG2SUBT_LOCK(mpeg2subt) \
  {g_mutex_lock ((mpeg2subt)->lock);}
#define GST_MPEG2SUBT_UNLOCK(mpeg2subt) \
  {g_mutex_unlock ((mpeg2subt)->lock);}
#define GST_MPEG2SUBT_COND_WAIT(mpeg2subt, cond) \
  {g_cond_wait (cond, (mpeg2subt)->lock);}

#endif /* GST_MPEG2SUBT_DEBUG_LOCKING */

typedef struct _GstMpeg2Subt GstMpeg2Subt;
typedef struct _GstMpeg2SubtClass GstMpeg2SubtClass;

/* Hold premultiplied colour values */
typedef struct YUVA_val {
  guint16 Y;
  guint16 U;
  guint16 V;
  guint16 A;
} YUVA_val;

struct _GstMpeg2Subt {
  GstElement element;

  GMutex *lock;			/* A lock to protect the element's
				   internal data structures. */

  GstPad *videopad, *subtitlepad, *srcpad;

  GstMiniObject *data;		/* Buffer or event being passed from
				   the video chain or event function
				   to the loop function. */
  GCond *data_received;		/* A new video frame was stored in
				   current_frame by the push
				   function. */
  GCond *data_processed;	/* The video frame in current_frame
				   was processed by the loop
				   function. */
  gboolean flushing;		/* TRUE if the element is flushing. */

  GstBuffer *partialbuf;	/* Collect together subtitle buffers
                                   until we have a full control
                                   sequence. */
  GQueue *subt_queue;		/* Queue of subtitle control sequences
                                   and events pending for display. */

  GstBuffer *last_frame;	/* Last video frame seen. */

  guchar *cur_cmds;		/* Block of SPU commands to
				   execute next. */
  GstBuffer *cur_cmds_buf;	/* Buffer containing the cur_cmds
				   block. */
  GstClockTime cur_cmds_time;	/* Time at which the current command
				   block must be executed. */

  GstBuffer *current_buf;	/* The packet containing the currently
				   active SPU image. */
  gint offset[2];		/* Offsets in the packet of the top
				   and bottom fields of the SPU
				   image. */

  gboolean display;		/* TRUE if the current SPU image
				   should be displayed. */
  gboolean hide;		/* TRUE if subpictures should be
				   hidden and only shown when forced
				   display is active. */
  gboolean forced_display;	/* TRUE if menu forced display was
				   activated. */

  gboolean still;		/* TRUE if a still frame is being
				   played. */
  GstClockTime still_ts;	/* Last timestamp used for displaying
				   the still frame. */
  GstClockTime still_stop;	/* Stop time for the current still
				   frame or GST_CLOCK_TIME_NULL for
				   unlimited still frames. */

  GstClockTime last_video_ts;	/* Last video timestamp sent down the
				   pipeline. Used for playback gap
				   checking. */
  gint adjusted_count;		/* Count of adjusted frames in
				   sequence. */

  /* 
   * Store 1 line width of U, V and A respectively.
   * Y is composited direct onto the frame.
   */
  guint16 *out_buffers[3];

  guint32 current_clut[16];	/* Color LookUp Table. */

  guchar subtitle_index[4];	/* Standard color palette. */
  guchar menu_index[4];		/* Highlight color palette. */
  guchar subtitle_alpha[4];	/* Standard alpha palette. */
  guchar menu_alpha[4];		/* Highlight alpha palette. */

  /* Keep premultiplied color values. */
  YUVA_val palette_cache[4];
  YUVA_val highlight_palette_cache[4];

  gint left, top,
    right, bottom;		/* Current SPU image position and
				   size. */
  gint clip_left, clip_top,
    clip_right, clip_bottom;	/* Highlight area position and
				   size. */

  gint frame_numerator;		/* Frame rate numerator. */
  gint frame_denominator;	/* Frame rate denominator. */

  GstSegment video_segment;	/* Segment object to keep track of
				   segment changes in the video
				   stream. */
  GstSegment subtitle_segment;	/* Segment object to keep track of
				   segment changes in the subtitle
				   stream. */

  gint in_width, in_height;
  gint current_button;
};

struct _GstMpeg2SubtClass {
  GstElementClass parent_class;
};

GType gst_mpeg2subt_get_type(void);


#ifdef __cplusplus
}
#endif /* __cplusplus */


#endif /* __GST_MPEG2SUBT_H__ */
