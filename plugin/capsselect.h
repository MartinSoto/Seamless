/* GStreamer
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
 *
 * capsselect.h: Automatically select the output pad based on the
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

#ifndef __CAPSSELECT_H__
#define __CAPSSELECT_H__

#include <gst/gst.h>

G_BEGIN_DECLS


#define GST_TYPE_CAPSSELECT \
  (capsselect_get_type())
#define CAPSSELECT(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_CAPSSELECT,CapsSelect))
#define CAPSSELECT_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_CAPSSELECT,CapsSelectClass))
#define GST_IS_CAPSSELECT(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_CAPSSELECT))
#define GST_IS_CAPSSELECT_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_CAPSSELECT))


typedef struct _CapsSelect CapsSelect;
typedef struct _CapsSelectClass CapsSelectClass;


typedef enum {
  CAPSSELECT_OPEN = GST_ELEMENT_FLAG_LAST,
  CAPSSELECT_FLAG_LAST
} CapsSelectFlags;


struct _CapsSelect {
  GstElement element;

  GstPad *sink;		/* Sink pad. */
  GArray *srcs;		/* Array containing the source pads. */

  GstPad *cur_src;	/* The source pad we are currently writing
                           to. */
  GstCaps *cur_caps;	/* The caps currently set for the sink. */
};


struct _CapsSelectClass {
  GstElementClass parent_class;

  /* Signals */
};


extern GType	capsselect_get_type		(void);

G_END_DECLS

#endif /* __CAPSSELECT_H__ */
