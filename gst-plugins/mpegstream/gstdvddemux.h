/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
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


#ifndef __DVD_DEMUX_H__
#define __DVD_DEMUX_H__


#include <gst/gst.h>
#include "gstmpegdemux.h"


#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */


#define GST_TYPE_DVD_DEMUX \
  (gst_dvd_demux_get_type())
#define GST_DVD_DEMUX(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_DVD_DEMUX,GstDVDDemux))
#define GST_DVD_DEMUX_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_DVD_DEMUX,GstDVDDemuxClass))
#define GST_IS_DVD_DEMUX(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_DVD_DEMUX))
#define GST_IS_DVD_DEMUX_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_DVD_DEMUX))


/* Supported kinds of streams in addition to what mpegdemux already
   does. */
enum {
  GST_DVD_DEMUX_STREAM_SUBPICTURE = GST_MPEG_DEMUX_STREAM_LAST,
  GST_DVD_DEMUX_STREAM_LAST
};

/* Supported number of streams. */
#define GST_DVD_DEMUX_NUM_SUBPICTURE_STREAMS 	32
#define GST_DVD_DEMUX_MAX_SUBPICTURE_DELAY 0

typedef struct _GstDVDLPCMStream GstDVDLPCMStream ;
typedef struct _GstDVDDemux GstDVDDemux;
typedef struct _GstDVDDemuxClass GstDVDDemuxClass;


/* Additional recognized audio types. */
enum {
  GST_DVD_DEMUX_AUDIO_LPCM = GST_MPEG_DEMUX_AUDIO_LAST,
  GST_DVD_DEMUX_AUDIO_AC3,
  GST_DVD_DEMUX_AUDIO_DTS,
  GST_DVD_DEMUX_AUDIO_LAST
};


/* The recognized subpicture types. */
enum {
  GST_DVD_DEMUX_SUBP_UNKNOWN =
    GST_MPEG_DEMUX_STREAM_TYPE (GST_DVD_DEMUX_STREAM_SUBPICTURE, 1),
  GST_DVD_DEMUX_SUBP_DVD,
  GST_DVD_DEMUX_SUBP_LAST
};


/* Extended structure to hold additional information for linear PCM
   streams. */
struct _GstDVDLPCMStream {
  GstMPEGStream	 parent;
  guint8	 sample_info;	/* The type of linear PCM samples
                                   associated to this stream. The
                                   values are bit fields with the same
                                   format of the sample_info field in
                                   the linear PCM header. */
};


struct _GstDVDDemux {
  GstMPEGDemux	 parent;

  GstPad *cur_video;		/* Current video stream pad. */
  GstPad *cur_audio;		/* Current audio stream pad. */
  GstPad *cur_subpicture;	/* Current subpicture stream pad. */

  gint cur_video_nr;		/* Current video stream number. */
  gint cur_audio_nr;		/* Current audio stream number. */
  gint cur_subpicture_nr;	/* Current subpicture stream number. */

  GstClockTime last_end_ptm;	/* End presentation time of the last nav packet
                                   event received. */

  gboolean just_flushed;	/* The element just received a flush event. */
  GstClockTime discont_time;	/* If different from GST_CLOCK_TIME_NONE, a
                                   discontinuous event should be sent with the
                                   given time, before sending the next dara
                                   block. */

  gint mpeg_version;		/* Version of the MPEG video stream */

  GstMPEGStream *subpicture_stream[GST_DVD_DEMUX_NUM_SUBPICTURE_STREAMS];
				/* Subpicture output streams. */
  GstClockTime   subpicture_time[GST_DVD_DEMUX_NUM_SUBPICTURE_STREAMS];
  				/* Last timestamp for buffer on each stream. */
};


struct _GstDVDDemuxClass {
  GstMPEGDemuxClass parent_class;

  GstPadTemplate *cur_video_template;
  GstPadTemplate *cur_audio_template;
  GstPadTemplate *subpicture_template;
  GstPadTemplate *cur_subpicture_template;

  GstMPEGStream *
  		(*get_subpicture_stream)(GstMPEGDemux *mpeg_demux,
                                         guint8 stream_nr,
                                         gint type,
                                         const gpointer info);
};


GType		gst_dvd_demux_get_type		(void);

gboolean 	gst_dvd_demux_plugin_init 	(GstPlugin *plugin);


#ifdef __cplusplus
}
#endif /* __cplusplus */


#endif /* __DVD_DEMUX_H__ */
