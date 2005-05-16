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

  GstPad *videopad,*subtitlepad,*srcpad;

  GstBuffer *partialbuf;	/* Collect together subtitle buffers
                                   until we have a full control
                                   sequence. */
  GQueue *subt_queue;		/* Queue of subtitle control sequences
                                   pending for display. */
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
  gboolean forced_display;	/* TRUE if menu forced display was
				   activated. */

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
