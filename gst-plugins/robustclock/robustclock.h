/* Seamless DVD Player
 * Copyright (C) 2004-2005 Martin Soto <martinsoto@users.sourceforge.net>
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

#ifndef __GST_ROBUST_CLOCK_H__
#define __GST_ROBUST_CLOCK_H__

#include <gst/gst.h>

G_BEGIN_DECLS

#define GST_TYPE_ROBUST_CLOCK \
  (gst_robust_clock_get_type())
#define GST_ROBUST_CLOCK(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_ROBUST_CLOCK,GstRobustClock))
#define GST_ROBUST_CLOCK_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_ROBUST_CLOCK,GstRobustClockClass))
#define GST_IS_ROBUST_CLOCK(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_ROBUST_CLOCK))
#define GST_IS_ROBUST_CLOCK_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_ROBUST_CLOCK))


typedef struct _GstRobustClock GstRobustClock;
typedef struct _GstRobustClockClass GstRobustClockClass;

struct _GstRobustClock {
  GstClock parent;

  /* Private: */
  GstClock *wrapped;		/* The wrapped clock. */
  GstClockClass *wrapped_class;	/* The class of the wrapped clock. */

  GstClockTime last_system;	/* Last time seen from the system
                                   clock. */
  GstClockTime system_last_progress;	
                                /* System time observed the last time
				   the wrapped clock progresed. */
  GstClockTime last_wrapped;	/* Last time seen from the wrapped
                                   clock. */

  GstClockTimeDiff adjust;	/* Adjust value to add to the wrapped
                                   clock. */
  GstClockTimeDiff stall_adjust;
  				/* Adjust value corresponding to the
				   current stall period. */

  GstClockTime last_value;	/* Last time value returned by the
				   clock. */
};

struct _GstRobustClockClass {
  GstSystemClockClass parent_class;

  gpointer _gst_reserved[GST_PADDING];
};


GType
gst_robust_clock_get_type (void);

GstClock*
gst_robust_clock_new (GstClock *wrapped);


G_END_DECLS

#endif /* __GST_ROBUST_CLOCK_H__ */
