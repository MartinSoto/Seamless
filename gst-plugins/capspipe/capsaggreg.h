/* GStreamer
 * Copyright (C) 2004-2005 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * capsaggreg.h: Aggregate contents from multiple sink pads into a 
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

#ifndef __CAPSAGGREG_H__
#define __CAPSAGGREG_H__

#include <gst/gst.h>

G_BEGIN_DECLS


#define GST_TYPE_CAPSAGGREG \
  (capsaggreg_get_type())
#define CAPSAGGREG(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_CAPSAGGREG,CapsAggreg))
#define CAPSAGGREG_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_CAPSAGGREG,CapsAggregClass))
#define GST_IS_CAPSAGGREG(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_CAPSAGGREG))
#define GST_IS_CAPSAGGREG_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_CAPSAGGREG))


typedef struct _CapsAggreg CapsAggreg;
typedef struct _CapsAggregClass CapsAggregClass;


typedef enum {
  CAPSAGGREG_OPEN = GST_ELEMENT_FLAG_LAST,
  CAPSAGGREG_FLAG_LAST
} CapsAggregFlags;


struct _CapsAggreg {
  GstElement element;

  GList *sinks;		/* Array containing the sink pads. */
  GstPad *src;		/* Src pad. */

  GstPad *cur_sink;	/* The sink pad we are currently reading
                           from. */
};


struct _CapsAggregClass {
  GstElementClass parent_class;

  /* Signals */
};


extern GType	capsaggreg_get_type		(void);

G_END_DECLS

#endif /* __CAPSAGGREG_H__ */
