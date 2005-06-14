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

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include "robustclock.h"


GST_DEBUG_CATEGORY_STATIC (robustclock_debug);
#define GST_CAT_DEFAULT (robustclock_debug)


/* Maximum acceptable time for the wrapped clock to be stalled. */
#define MAX_STALLED (GST_SECOND * 0.1)


static void
 gst_robust_clock_class_init (GstRobustClockClass * klass);
static void
 gst_robust_clock_init (GstRobustClock * clock);

static gdouble
gst_robust_clock_change_speed (GstClock *clock, gdouble oldspeed,
    gdouble newspeed);
static gdouble
gst_robust_clock_get_speed (GstClock *clock);
static guint64
gst_robust_clock_change_resolution (GstClock *clock, guint64 old_resolution,
    guint64 new_resolution);
static guint64
gst_robust_clock_get_resolution (GstClock *clock);
static GstClockTime
gst_robust_clock_get_internal_time (GstClock *clock);
static GstClockEntryStatus
gst_robust_clock_wait (GstClock *clock, GstClockEntry *entry);
static GstClockEntryStatus
gst_robust_clock_wait_async (GstClock *clock, GstClockEntry *entry);
static void
gst_robust_clock_unschedule (GstClock *clock, GstClockEntry *entry);
static void
gst_robust_clock_unlock (GstClock *clock, GstClockEntry *entry);

static GstClockClass *parent_class = NULL;

/* static guint gst_robust_clock_signals[LAST_SIGNAL] = { 0 }; */

GType
gst_robust_clock_get_type (void)
{
  static GType clock_type = 0;

  if (!clock_type) {
    static const GTypeInfo clock_info = {
      sizeof (GstRobustClockClass),
      NULL,
      NULL,
      (GClassInitFunc) gst_robust_clock_class_init,
      NULL,
      NULL,
      sizeof (GstRobustClock),
      4,
      (GInstanceInitFunc) gst_robust_clock_init,
      NULL
    };

    clock_type = g_type_register_static (GST_TYPE_CLOCK,
        "GstRobustClock", &clock_info, 0);
  }

  return clock_type;
}


static void
gst_robust_clock_class_init (GstRobustClockClass * klass)
{
  GObjectClass *gobject_class;
  GstObjectClass *gstobject_class;
  GstClockClass *gstclock_class;

  gobject_class = (GObjectClass *) klass;
  gstobject_class = (GstObjectClass *) klass;
  gstclock_class = (GstClockClass *) klass;

  parent_class = g_type_class_ref (GST_TYPE_CLOCK);

  gstclock_class->change_speed = gst_robust_clock_change_speed;
  gstclock_class->get_speed = gst_robust_clock_get_speed;
  gstclock_class->change_resolution = gst_robust_clock_change_resolution;
  gstclock_class->get_resolution = gst_robust_clock_get_resolution;
  gstclock_class->get_internal_time = gst_robust_clock_get_internal_time;
  gstclock_class->wait = gst_robust_clock_wait;
  gstclock_class->wait_async = gst_robust_clock_wait_async;
  gstclock_class->unschedule = gst_robust_clock_unschedule;
  gstclock_class->unlock = gst_robust_clock_unlock;
}

static void
gst_robust_clock_init (GstRobustClock * clock)
{
  gst_object_set_name (GST_OBJECT (clock), "GstRobustClock");
}

GstClock *
gst_robust_clock_new (GstClock *wrapped)
{
  GstRobustClock *rclock =
      GST_ROBUST_CLOCK (g_object_new (GST_TYPE_ROBUST_CLOCK, NULL));

  rclock->wrapped = wrapped;
  rclock->wrapped_class = GST_CLOCK_GET_CLASS (wrapped);

  rclock->last_system = GST_CLOCK_TIME_NONE;
  rclock->system_last_progress = GST_CLOCK_TIME_NONE;
  rclock->last_wrapped = GST_CLOCK_TIME_NONE;

  rclock->adjust = 0;
  rclock->stall_adjust = 0;

  rclock->last_value = GST_CLOCK_TIME_NONE;

  return (GstClock *) rclock;
}


static gdouble
gst_robust_clock_change_speed (GstClock *clock, gdouble oldspeed,
    gdouble newspeed)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  return rclock->wrapped_class->change_speed (rclock->wrapped, oldspeed,
      newspeed);
}

static gdouble
gst_robust_clock_get_speed (GstClock *clock)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  return rclock->wrapped_class->get_speed (rclock->wrapped);
}

static guint64
gst_robust_clock_change_resolution (GstClock *clock, guint64 old_resolution,
    guint64 new_resolution)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  return rclock->wrapped_class->change_resolution (rclock->wrapped,
      old_resolution, new_resolution);
}

static guint64
gst_robust_clock_get_resolution (GstClock *clock)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  return rclock->wrapped_class->get_resolution (rclock->wrapped);
}

static GstClockTime
gst_robust_clock_get_internal_time (GstClock *clock)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);
  GTimeVal timeval;
  GstClockTime wrapped_time, system_time;
  GstClockTimeDiff interval;
  GstClockTime value;

  g_get_current_time (&timeval);
  system_time = GST_TIMEVAL_TO_TIME (timeval);
  wrapped_time = rclock->wrapped_class->get_internal_time (rclock->wrapped);

  if (rclock->last_wrapped != GST_CLOCK_TIME_NONE &&
      wrapped_time <= rclock->last_wrapped) {
    /* Wrapped clock is stalled, or went back. */

    interval = GST_CLOCK_DIFF (system_time, rclock->system_last_progress);
    if (interval > MAX_STALLED) {
      /* Progress as much as the system clock did since the last time
	 we were consulted. */
      rclock->stall_adjust = interval;
    }

    /* If the clock actually went back, compensate for the gap. */
    rclock->adjust += GST_CLOCK_DIFF (rclock->last_wrapped, wrapped_time);
  } else {
    rclock->system_last_progress = system_time;
    rclock->adjust += rclock->stall_adjust;
    rclock->stall_adjust = 0;
  }

  rclock->last_system = system_time;
  rclock->last_wrapped = wrapped_time;

  value = wrapped_time + rclock->adjust + rclock->stall_adjust;
  if (rclock->last_value != GST_CLOCK_TIME_NONE &&
      value < rclock->last_value) {
    g_return_val_if_reached (value);
  }

  rclock->last_value = value;
  return value;
}

static GstClockEntryStatus
gst_robust_clock_wait (GstClock *clock, GstClockEntry *entry)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  return rclock->wrapped_class->wait (rclock->wrapped, entry);
}

static GstClockEntryStatus
gst_robust_clock_wait_async (GstClock *clock, GstClockEntry *entry)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  return rclock->wrapped_class->wait_async (rclock->wrapped, entry);
}

static void
gst_robust_clock_unschedule (GstClock *clock, GstClockEntry *entry)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  rclock->wrapped_class->unschedule (rclock->wrapped, entry);
}

static void
gst_robust_clock_unlock (GstClock *clock, GstClockEntry *entry)
{
  GstRobustClock *rclock = GST_ROBUST_CLOCK (clock);

  rclock->wrapped_class->unlock (rclock->wrapped, entry);
}


static gboolean
plugin_init (GstPlugin * plugin)
{
  GST_DEBUG_CATEGORY_INIT (robustclock_debug, "robustclock", 1,
      "Robust clock wrapper");

  return TRUE;
}

GST_PLUGIN_DEFINE (GST_VERSION_MAJOR,
    GST_VERSION_MINOR,
    "robustclock",
    "Wrapper clock that never stops, even if the wrapped clock does",
    plugin_init,
    VERSION,
    "GPL",
    PACKAGE,
    "http://seamless.sourceforge.net");
