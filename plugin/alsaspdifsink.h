/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * alsaspdifsink.h: Audio sink for SP/DIF interfaces trough ALSA
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

#ifndef __ALSASPDIFSINK_H__
#define __ALSASPDIFSINK_H__

#include <gst/gst.h>

#define ALSA_PCM_NEW_HW_PARAMS_API
#define ALSA_PCM_NEW_SW_PARAMS_API
#include <alsa/asoundlib.h>


G_BEGIN_DECLS

#define GST_TYPE_ALSASPDIFSINK \
  (alsaspdifsink_get_type())
#define ALSASPDIFSINK(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_ALSASPDIFSINK,AlsaSPDIFSink))
#define ALSASPDIFSINK_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_ALSASPDIFSINK,AlsaSPDIFSinkClass))
#define GST_IS_ALSASPDIFSINK(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_ALSASPDIFSINK))
#define GST_IS_ALSASPDIFSINK_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_ALSASPDIFSINK))
#define GST_TYPE_ALSASPDIFSINK (alsaspdifsink_get_type())


typedef struct _AlsaSPDIFSink AlsaSPDIFSink;
typedef struct _AlsaSPDIFSinkClass AlsaSPDIFSinkClass;


typedef enum {
  ALSASPDIFSINK_OPEN = GST_ELEMENT_FLAG_LAST,
  ALSASPDIFSINK_FLAG_LAST  = GST_ELEMENT_FLAG_LAST + 2,
} AlsaSPDIFSinkFlags;


/* ALSA spdif types. */
enum {
  SPDIF_NONE = 0,
  SPDIF_CON,
  SPDIF_PRO,
  SPDIF_PCM
};


/* ALSA output information. */
typedef struct {
  const char *pcm_name;   
  const char *card;
  int bits;
  int rate;
  int channels;
  int quiet;
  int spdif;
} AlsaSPDIFSinkOutput;


struct _AlsaSPDIFSink {
  GstElement element;

  GstPad *sinkpad;		/* The audio sink pad. */

  GstClockTime cur_ts;		/* Current time stamp. */

  AlsaSPDIFSinkOutput out_config;
				/* Output information. */
  snd_pcm_t *pcm;		/* ALSA output device. */

  gboolean passtrough;		/* Is the element in pass through
                                   digital mode? */

  GstClock *clock;		/* The clock for this element. */
  GstClock *provided_clock;	/* The clock provided by this element. */

  GstClockTime clock_time;	/* Current provided clock time,
                                   without hardware buffer delay. */
};


struct _AlsaSPDIFSinkClass {
  GstElementClass parent_class;
};


extern GType	alsaspdifsink_get_type		(void);

G_END_DECLS

#endif /* __DXR3AUDIOINK_H__ */
