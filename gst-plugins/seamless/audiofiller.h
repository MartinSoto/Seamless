/* Seamless DVD Player
 * Copyright (C) 2004-2006 Martin Soto <martinsoto@users.sourceforge.net>
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

#ifndef __AUDIOFILLER_H__
#define __AUDIOFILLER_H__

#include <gst/gst.h>
#include <gst/base/gstbasetransform.h>


G_BEGIN_DECLS


#define GST_TYPE_AUDIOFILLER \
  (audiofiller_get_type())
#define AUDIOFILLER(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_AUDIOFILLER,AudioFiller))
#define AUDIOFILLER_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_AUDIOFILLER,AudioFillerClass))
#define GST_IS_AUDIOFILLER(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_AUDIOFILLER))
#define GST_IS_AUDIOFILLER_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_AUDIOFILLER))
#define GST_TYPE_AUDIOFILLER (audiofiller_get_type())


typedef struct _AudioFiller AudioFiller;
typedef struct _AudioFillerClass AudioFillerClass;


typedef enum {
  AUDIOFILLER_OPEN = GST_ELEMENT_FLAG_LAST,
  AUDIOFILLER_FLAG_LAST
} AudioFillerFlags;


struct _AudioFiller {
  GstBaseTransform element;
};


struct _AudioFillerClass {
  GstBaseTransformClass parent_class;

  /* Signals */
};


extern GType
audiofiller_get_type (void);

G_END_DECLS

#endif /* __AUDIOFILLER__ */
