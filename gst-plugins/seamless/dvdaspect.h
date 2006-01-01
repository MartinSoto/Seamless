/* Seamless DVD Player
 * Copyright (C) 2005-2006 Martin Soto <martinsoto@users.sourceforge.net>
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

#ifndef __DVDASPECT_H__
#define __DVDASPECT_H__

#include <gst/gst.h>
#include <gst/base/gstbasetransform.h>


G_BEGIN_DECLS


#define GST_TYPE_DVDASPECT \
  (dvdaspect_get_type())
#define DVDASPECT(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_DVDASPECT,DVDAspect))
#define DVDASPECT_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_DVDASPECT,DVDAspectClass))
#define GST_IS_DVDASPECT(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_DVDASPECT))
#define GST_IS_DVDASPECT_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_DVDASPECT))
#define GST_TYPE_DVDASPECT (dvdaspect_get_type())


typedef struct _DVDAspect DVDAspect;
typedef struct _DVDAspectClass DVDAspectClass;


typedef enum {
  DVDASPECT_OPEN = GST_ELEMENT_FLAG_LAST,
  DVDASPECT_FLAG_LAST
} DVDAspectFlags;


struct _DVDAspect {
  GstBaseTransform element;

  GstCaps *sink_caps;	/* Current input caps. */
  GstCaps *src_caps;	/* Current output caps. */

  gint aspect_n;	/* Forced aspect ratio (numerator). */
  gint aspect_d;	/* Forced aspect ratio (denominator). 0 means
			   no forced aspect set. */
};


struct _DVDAspectClass {
  GstBaseTransformClass parent_class;

  /* Signals */
};


extern GType
dvdaspect_get_type (void);

G_END_DECLS

#endif /* __DVDASPECT__ */
