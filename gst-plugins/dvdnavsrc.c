/* GStreamer
 * Copyright (C) 2002 David I. Lehn <dlehn@users.sourceforge.net>
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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>
#include <assert.h>

#include "config.h"

#include <gst/gst.h>

#include <dvdnav/dvdnav.h>
#include <dvdread/nav_print.h>

#include "dvdnavsrcmarshal.h"


/**
 * Call a dvdnav function and report an error if it fails.
 */
#define DVDNAVSRC_CALL(func, params, elem) \
  if (func params != DVDNAV_STATUS_OK) { \
    gst_element_error (GST_ELEMENT (elem), \
      #func " error: %s\n", \
      dvdnav_err_to_string ((elem)->dvdnav)); \
  }

/* The maxinum number of audio and SPU streams in a DVD. */
#define DVDNAVSRC_MAX_AUDIO_STREAMS 8
#define DVDNAVSRC_MAX_SPU_STREAMS 16

#define GST_TYPE_DVDNAVSRC \
  (dvdnavsrc_get_type())
#define DVDNAVSRC(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_DVDNAVSRC,DVDNavSrc))
#define DVDNAVSRC_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_DVDNAVSRC,DVDNavSrcClass))
#define GST_IS_DVDNAVSRC(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_DVDNAVSRC))
#define GST_IS_DVDNAVSRC_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_DVDNAVSRC))
#define GST_TYPE_DVDNAVSRC (dvdnavsrc_get_type())

typedef struct _DVDNavSrc DVDNavSrc;
typedef struct _DVDNavSrcClass DVDNavSrcClass;

/* The pause modes to handle still frames. */
typedef enum {
  DVDNAVSRC_PAUSE_OFF,       /* No pause active. */
  DVDNAVSRC_PAUSE_LIMITED,   /* A time limited pause is active. */
  DVDNAVSRC_PAUSE_UNLIMITED  /* An time unlimited pause is active. */
} DVDNavSrcPauseMode;

/* Interval of time to sleep during pauses. */
#define DVDNAVSRC_PAUSE_INTERVAL (GST_SECOND / 5)

/* The DVD domain types. */
typedef enum {
  DVDNAVSRC_DOMAIN_UNKNOWN,  /* Unknown domain.  */
  DVDNAVSRC_DOMAIN_FP,       /* First Play domain. */
  DVDNAVSRC_DOMAIN_VMGM,     /* Video Management Menu domain */
  DVDNAVSRC_DOMAIN_VTSM,     /* Video Title Menu domain. */
  DVDNAVSRC_DOMAIN_VTS,      /* Video Title domain. */
} DVDNavSrcDomainType;

struct _DVDNavSrc {
  GstElement element;

  /* Pads */
  GstPad *srcpad;
  GstCaps *streaminfo;

  /* Location */
  gchar *location;

  gboolean did_seek;
  gboolean need_flush;
  gboolean need_discont;
  GstBufferPool *bufferpool;

  /* Timing */
  GstClock *clock;                /* The clock for this element. */

  /* Pause handling */
  DVDNavSrcPauseMode pause_mode;  /* The current pause mode. */
  GstClockTime pause_end;         /* The clock time for the end of the
                                     pause. */

  /* Highligh handling */
  int button;                     /* The currently highlighted button
                                     number (0 if no highlight). */
  dvdnav_highlight_area_t area;   /* The area corresponding to the
                                     currently highlighted button. */

  /* State handling */
  DVDNavSrcDomainType domain;     /* The current DVD domain. */

  int title, chapter, angle;

  dvdnav_t *dvdnav;               /* The libdvdnav handle. */

  GstCaps *buttoninfo;

  guint32 last_vobu_end;
};

struct _DVDNavSrcClass {
  GstElementClass parent_class;

  void (*button_pressed)	(DVDNavSrc *src, int button);
  void (*pointer_select)	(DVDNavSrc *src, int x, int y);
  void (*pointer_activate)	(DVDNavSrc *src, int x, int y);
  void (*user_op)		(DVDNavSrc *src, int op);
  void (*spu_clut_change)	(DVDNavSrc *src, void *clut);
  void (*vts_change)		(DVDNavSrc *src, int old_vtsN, int new_vtsN);
  void (*audio_stream_change)	(DVDNavSrc *src, int physical, int logical);
  void (*spu_stream_change)	(DVDNavSrc *src, int physical_wide,
                                 int physical_letterbox, int physical_pan_scan,
                                 int logical);
  void (*spu_highlight)		(DVDNavSrc *src, int button, int display,
                                 unsigned palette, unsigned sx, unsigned sy,
                                 unsigned ex, unsigned ey, unsigned pts);
  void (*channel_hop)		(DVDNavSrc *src);
};

/* elementfactory information */
static GstElementDetails dvdnavsrc_details = {
  "DVD Source and Navigation Element",
  "Source/File/DVD",
  "Access a DVD with navigation features using libdvdnav (SotoVersion2)",
  "David I. Lehn <dlehn@users.sourceforge.net>"
};


/* DVDNavSrc signals and  args */
enum {
  BUTTON_PRESSED_SIGNAL,
  POINTER_SELECT_SIGNAL,
  POINTER_ACTIVATE_SIGNAL,
  USER_OP_SIGNAL,
  SPU_CLUT_CHANGE_SIGNAL,
  VTS_CHANGE_SIGNAL,
  AUDIO_STREAM_CHANGE_SIGNAL,
  SPU_STREAM_CHANGE_SIGNAL,
  SPU_HIGHLIGHT_SIGNAL,
  CHANNEL_HOP_SIGNAL,
  LAST_SIGNAL
};

enum {
  ARG_0,
  ARG_LOCATION,
  ARG_STREAMINFO,
  ARG_BUTTONINFO,
  ARG_TITLE_STRING,
  ARG_TITLE,
  ARG_CHAPTER,
  ARG_ANGLE,
  ARG_AUDIO_LANGS,
  ARG_AUDIO_LANG,
  ARG_SPU_LANGS,
  ARG_SPU_LANG
};

typedef enum {
  DVDNAVSRC_OPEN		= GST_ELEMENT_FLAG_LAST,

  DVDNAVSRC_FLAG_LAST		= GST_ELEMENT_FLAG_LAST+2,
} DVDNavSrcFlags;


GType			dvdnavsrc_get_type	(void);
static void		dvdnavsrc_base_init	(gpointer g_class);
static void 		dvdnavsrc_class_init	(DVDNavSrcClass *klass);
static void 		dvdnavsrc_init		(DVDNavSrc *dvdnavsrc);

static void 		dvdnavsrc_set_property		(GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec);
static void 		dvdnavsrc_get_property		(GObject *object, guint prop_id, GValue *value, GParamSpec *pspec);

static void             dvdnavsrc_set_clock     (GstElement *element,
                                                 GstClock *clock);
static void		dvdnavsrc_wait		(DVDNavSrc *src,
                                                 GstClockTime time);

static GstData *	dvdnavsrc_get		(GstPad *pad);
/*static GstBuffer *	dvdnavsrc_get_region	(GstPad *pad,gulong offset,gulong size); */
static gboolean 	dvdnavsrc_event 		(GstPad *pad, GstEvent *event);
static const GstEventMask*
			dvdnavsrc_get_event_mask 	(GstPad *pad);
static const GstFormat*
			dvdnavsrc_get_formats 		(GstPad *pad);
/*static gboolean 	dvdnavsrc_convert 		(GstPad *pad,
				    			 GstFormat src_format,
				    			 gint64 src_value, 
							 GstFormat *dest_format, 
							 gint64 *dest_value);*/
static gboolean 	dvdnavsrc_query 		(GstPad *pad, GstQueryType type,
		     					 GstFormat *format, gint64 *value);
static const GstQueryType*
			dvdnavsrc_get_query_types 	(GstPad *pad);

static gboolean		dvdnavsrc_close		(DVDNavSrc *src);
static gboolean		dvdnavsrc_open		(DVDNavSrc *src);
static gboolean		dvdnavsrc_is_open	(DVDNavSrc *src);
static void		dvdnavsrc_print_event	(DVDNavSrc *src, guint8 *data, int event, int len);
static void		dvdnavsrc_update_streaminfo (DVDNavSrc *src);
static void		dvdnavsrc_update_buttoninfo (DVDNavSrc *src);
static void             dvdnavsrc_set_domain    (DVDNavSrc *src);
static void             dvdnavsrc_reset_highlight (DVDNavSrc *src);
static void             dvdnavsrc_update_highlight  (DVDNavSrc *src);
static void		dvdnavsrc_button_pressed (DVDNavSrc *src, int button);
static void		dvdnavsrc_pointer_select (DVDNavSrc *src, int x, int y);
static void		dvdnavsrc_pointer_activate (DVDNavSrc *src, int x, int y);
static void		dvdnavsrc_user_op (DVDNavSrc *src, int op);
static void		dvdnavsrc_real_user_op (DVDNavSrc *src, int op);
static void 		dvdnavsrc_spu_clut_change (DVDNavSrc *src,
                                                   void *clut);
static void 		dvdnavsrc_vts_change (DVDNavSrc *src,
                                              int old_vtsN,
                                              int new_vtsN);
static void 		dvdnavsrc_audio_stream_change (DVDNavSrc *src,
                                                       int physical,
                                                       int logical);
static void 		dvdnavsrc_spu_stream_change (DVDNavSrc *src,
                                                     int physical_wide,
                                                     int physical_letterbox,
                                                     int physical_pan_scan,
                                                     int logical);
static void             dvdnavsrc_spu_highlight (DVDNavSrc *src, int button,
                                                 int display, unsigned palette,
                                                 unsigned sx, unsigned sy,
                                                 unsigned ex, unsigned ey,
                                                 unsigned pts);
static void		dvdnavsrc_channel_hop	(DVDNavSrc *src);
static GstElementStateReturn 	dvdnavsrc_change_state 	(GstElement *element);


static GstElementClass *parent_class = NULL;
static guint dvdnavsrc_signals[LAST_SIGNAL] = { 0 };

static GstFormat sector_format;
static GstFormat title_format;
static GstFormat chapter_format;
static GstFormat angle_format;

GType
dvdnavsrc_get_type (void) 
{
  static GType dvdnavsrc_type = 0;

  if (!dvdnavsrc_type) {
    static const GTypeInfo dvdnavsrc_info = {
      sizeof(DVDNavSrcClass),
      dvdnavsrc_base_init,
      NULL,
      (GClassInitFunc)dvdnavsrc_class_init,
      NULL,
      NULL,
      sizeof(DVDNavSrc),
      0,
      (GInstanceInitFunc)dvdnavsrc_init,
    };
    dvdnavsrc_type = g_type_register_static (GST_TYPE_ELEMENT, "DVDNavSrc", &dvdnavsrc_info, 0);

    sector_format = gst_format_register ("sector", "DVD sector");
    title_format = gst_format_register ("title", "DVD title");
    chapter_format = gst_format_register ("chapter", "DVD chapter");
    angle_format = gst_format_register ("angle", "DVD angle");
  }
  return dvdnavsrc_type;
}

static void
dvdnavsrc_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &dvdnavsrc_details);
}

static void
dvdnavsrc_class_init (DVDNavSrcClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;

  gobject_class = (GObjectClass*)klass;
  gstelement_class = (GstElementClass*)klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

  dvdnavsrc_signals[BUTTON_PRESSED_SIGNAL] =
    g_signal_new ("button_pressed",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, button_pressed),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT,
        G_TYPE_NONE, 1,
        G_TYPE_INT);

  dvdnavsrc_signals[POINTER_SELECT_SIGNAL] =
    g_signal_new ("pointer_select",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, pointer_select),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT_INT,
        G_TYPE_NONE, 2,
        G_TYPE_INT, G_TYPE_INT);

  dvdnavsrc_signals[POINTER_ACTIVATE_SIGNAL] =
    g_signal_new ("pointer_activate",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, pointer_activate),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT_INT,
        G_TYPE_NONE, 2,
        G_TYPE_INT, G_TYPE_INT);

  dvdnavsrc_signals[USER_OP_SIGNAL] =
    g_signal_new ("user_op",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, user_op),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT,
        G_TYPE_NONE, 1,
        G_TYPE_INT);

  dvdnavsrc_signals[SPU_CLUT_CHANGE_SIGNAL] =
    g_signal_new ("spu_clut_change",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, spu_clut_change),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__POINTER,
        G_TYPE_NONE, 1,
        G_TYPE_POINTER);

  dvdnavsrc_signals[VTS_CHANGE_SIGNAL] =
    g_signal_new ("vts_change",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, vts_change),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT_INT,
        G_TYPE_NONE, 2,
        G_TYPE_INT, G_TYPE_INT);

  dvdnavsrc_signals[AUDIO_STREAM_CHANGE_SIGNAL] =
    g_signal_new ("audio_stream_change",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, audio_stream_change),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT_INT,
        G_TYPE_NONE, 2,
        G_TYPE_INT, G_TYPE_INT);

  dvdnavsrc_signals[SPU_STREAM_CHANGE_SIGNAL] =
    g_signal_new ("spu_stream_change",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, spu_stream_change),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT_INT_INT_INT,
        G_TYPE_NONE, 4,
        G_TYPE_INT, G_TYPE_INT, G_TYPE_INT, G_TYPE_INT);

  dvdnavsrc_signals[SPU_HIGHLIGHT_SIGNAL] =
    g_signal_new ("spu_highlight",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, spu_highlight),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__INT_INT_UINT_UINT_UINT_UINT_UINT_UINT,
        G_TYPE_NONE, 8,
        G_TYPE_INT, G_TYPE_INT, G_TYPE_UINT, G_TYPE_UINT,
        G_TYPE_UINT, G_TYPE_UINT, G_TYPE_UINT, G_TYPE_UINT);

  dvdnavsrc_signals[CHANNEL_HOP_SIGNAL] =
    g_signal_new ("channel_hop",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST | G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDNavSrcClass, channel_hop),
        NULL, NULL,
        dvdnavsrc_marshal_VOID__VOID,
        G_TYPE_NONE, 0);

  klass->button_pressed = dvdnavsrc_button_pressed;
  klass->pointer_select = dvdnavsrc_pointer_select;
  klass->pointer_activate = dvdnavsrc_pointer_activate;
  klass->user_op = dvdnavsrc_user_op;
  klass->spu_clut_change = dvdnavsrc_spu_clut_change;
  klass->vts_change = dvdnavsrc_vts_change;
  klass->audio_stream_change = dvdnavsrc_audio_stream_change;
  klass->spu_stream_change = dvdnavsrc_spu_stream_change;
  klass->spu_highlight = dvdnavsrc_spu_highlight;
  klass->channel_hop = dvdnavsrc_channel_hop;
    
  g_object_class_install_property(gobject_class, ARG_LOCATION,
    g_param_spec_string("location", "location", "location",
                        NULL, G_PARAM_READWRITE));
  g_object_class_install_property(gobject_class, ARG_TITLE_STRING,
    g_param_spec_string("title_string", "title string", "DVD title string",
                        NULL, G_PARAM_READABLE));
  g_object_class_install_property(gobject_class, ARG_TITLE,
    g_param_spec_int("title", "title", "title",
                     0,99,1,G_PARAM_READWRITE));
  g_object_class_install_property(gobject_class, ARG_CHAPTER,
    g_param_spec_int("chapter", "chapter", "chapter",
                     1,99,1,G_PARAM_READWRITE));
  g_object_class_install_property(gobject_class, ARG_ANGLE,
    g_param_spec_int("angle", "angle", "angle",
                     1,9,1,G_PARAM_READWRITE));
  g_object_class_install_property(gobject_class, ARG_STREAMINFO,
    g_param_spec_boxed("streaminfo", "streaminfo", "streaminfo",
                       GST_TYPE_CAPS, G_PARAM_READABLE));
  g_object_class_install_property(gobject_class, ARG_BUTTONINFO,
    g_param_spec_boxed("buttoninfo", "buttoninfo", "buttoninfo",
                       GST_TYPE_CAPS, G_PARAM_READABLE));
  g_object_class_install_property(gobject_class, ARG_AUDIO_LANGS,
    g_param_spec_string("audio_languages", "audio_languages",
                        "Available audio languages",
                        NULL, G_PARAM_READABLE));
  g_object_class_install_property(gobject_class, ARG_AUDIO_LANG,
    g_param_spec_string("audio_language", "audio_language",
                        "Current audio language",
                        NULL, G_PARAM_READABLE));
  g_object_class_install_property(gobject_class, ARG_SPU_LANGS,
    g_param_spec_string("spu_languages", "spu_languages",
                        "Available SPU languages",
                        NULL, G_PARAM_READABLE));
  g_object_class_install_property(gobject_class, ARG_SPU_LANG,
    g_param_spec_string("spu_language", "spu_language",
                        "Current SPU language",
                        NULL, G_PARAM_READABLE));

  gobject_class->set_property = GST_DEBUG_FUNCPTR(dvdnavsrc_set_property);
  gobject_class->get_property = GST_DEBUG_FUNCPTR(dvdnavsrc_get_property);

  gstelement_class->change_state = dvdnavsrc_change_state;
  gstelement_class->set_clock = dvdnavsrc_set_clock;
}

static void 
dvdnavsrc_init (DVDNavSrc *src) 
{
  src->srcpad = gst_pad_new ("src", GST_PAD_SRC);

  gst_pad_set_get_function (src->srcpad, dvdnavsrc_get);
  gst_pad_set_event_function (src->srcpad, dvdnavsrc_event);
  gst_pad_set_event_mask_function (src->srcpad, dvdnavsrc_get_event_mask);
  /*gst_pad_set_convert_function (src->srcpad, dvdnavsrc_convert);*/
  gst_pad_set_query_function (src->srcpad, dvdnavsrc_query);
  gst_pad_set_query_type_function (src->srcpad, dvdnavsrc_get_query_types);
  gst_pad_set_formats_function (src->srcpad, dvdnavsrc_get_formats);

  gst_element_add_pad (GST_ELEMENT (src), src->srcpad);

  src->bufferpool = gst_buffer_pool_get_default (DVD_VIDEO_LB_LEN, 2);

  src->clock = NULL;

  src->location = g_strdup("/dev/dvd");

  src->did_seek = FALSE;
  src->need_flush = FALSE;

  /* Pause mode is initially inactive. */
  src->pause_mode = DVDNAVSRC_PAUSE_OFF;

  /* No highlighted button. */
  src->button = 0;

  /* Domain is unknown at the begining. */
  src->domain = DVDNAVSRC_DOMAIN_UNKNOWN;

  src->title = 0;
  src->chapter = 0;
  src->angle = 1;
  src->streaminfo = NULL;
  src->buttoninfo = NULL;

  src->last_vobu_end = 0xffffff3e;
}

/* FIXME: this code is not being used */
#ifdef PLEASEFIXTHISCODE
static void
dvdnavsrc_destroy (DVDNavSrc *dvdnavsrc)
{
  /* FIXME */
  g_print("FIXME\n");
  gst_buffer_pool_destroy (dvdnavsrc->bufferpool);
}
#endif

static gboolean 
dvdnavsrc_is_open (DVDNavSrc *src)
{
  g_return_val_if_fail (src != NULL, FALSE);
  g_return_val_if_fail (GST_IS_DVDNAVSRC (src), FALSE);

  return GST_FLAG_IS_SET (src, DVDNAVSRC_OPEN);
}

static void 
dvdnavsrc_set_property (GObject *object, guint prop_id, const GValue *value, GParamSpec *pspec) 
{
  DVDNavSrc *src;

  /* it's not null if we got it, but it might not be ours */
  g_return_if_fail (GST_IS_DVDNAVSRC (object));
  
  src = DVDNAVSRC (object);

  switch (prop_id) {
    case ARG_LOCATION:
      /* the element must be stopped in order to do this */
      /*g_return_if_fail(!GST_FLAG_IS_SET(src,GST_STATE_RUNNING)); */

      if (src->location)
        g_free (src->location);
      /* clear the filename if we get a NULL (is that possible?) */
      if (g_value_get_string (value) == NULL)
        src->location = g_strdup("/dev/dvd");
      /* otherwise set the new filename */
      else
        src->location = g_strdup (g_value_get_string (value));  
      break;
    case ARG_TITLE:
      src->title = g_value_get_int (value);
      src->did_seek = TRUE;
      break;
    case ARG_CHAPTER:
      src->chapter = g_value_get_int (value);
      src->did_seek = TRUE;
      break;
    case ARG_ANGLE:
      src->angle = g_value_get_int (value);
      break;
    case ARG_AUDIO_LANG:
      if (dvdnavsrc_is_open(src)) {
        const gchar *code = g_value_get_string (value);
        if (code != NULL) {
          fprintf (stderr, "++++++ Setting language %s\n", code);
          if (dvdnav_audio_language_select (src->dvdnav, (char *) code) !=
              DVDNAV_STATUS_OK) {
            fprintf (stderr, "++++++ Error setting language: %s\n",
                     dvdnav_err_to_string (src->dvdnav));
          }
        }
      }
      break;
    case ARG_SPU_LANG:
      if (dvdnavsrc_is_open(src)) {
        const gchar *code = g_value_get_string (value);
        if (code != NULL) {
          dvdnav_spu_language_select (src->dvdnav, (char *) code);
        }
      }
      break;
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }

}

static void 
dvdnavsrc_get_property (GObject *object, guint prop_id, GValue *value, GParamSpec *pspec) 
{
  DVDNavSrc *src;
  const char *title_string;

  /* it's not null if we got it, but it might not be ours */
  g_return_if_fail (GST_IS_DVDNAVSRC (object));
  
  src = DVDNAVSRC (object);

  switch (prop_id) {
    case ARG_LOCATION:
      g_value_set_string (value, src->location);
      break;
    case ARG_STREAMINFO:
      g_value_set_boxed (value, src->streaminfo);
      break;
    case ARG_BUTTONINFO:
      g_value_set_boxed (value, src->buttoninfo);
      break;
    case ARG_TITLE_STRING:
      if (!dvdnavsrc_is_open(src)) {
        g_value_set_string (value, "");
      } else if (dvdnav_get_title_string(src->dvdnav, &title_string) !=
          DVDNAV_STATUS_OK) {
        g_value_set_string (value, "UNKNOWN");
      } else {
        g_value_set_string (value, title_string);
      }
      break;
    case ARG_TITLE:
      g_value_set_int (value, src->title);
      break;
    case ARG_CHAPTER:
      g_value_set_int (value, src->chapter);
      break;
    case ARG_ANGLE:
      g_value_set_int (value, src->angle);
      break;
    case ARG_AUDIO_LANGS:
      if (!dvdnavsrc_is_open(src)) {
        g_value_set_string (value, "");
      }
      else {
        uint8_t physical, logical;
        uint16_t lang_int;
        gchar langs[DVDNAVSRC_MAX_AUDIO_STREAMS * 3];
        gchar *lang_ptr = langs;
        
        for (physical = 0; physical < DVDNAVSRC_MAX_AUDIO_STREAMS;
             physical++) {
          logical = dvdnav_get_audio_logical_stream (src->dvdnav, physical);
          lang_int = dvdnav_audio_stream_to_lang (src->dvdnav, logical);
          if (lang_int != 0xffff) {
            lang_ptr[0] = (lang_int >> 8) & 0xff;
            lang_ptr[1] = lang_int & 0xff;
            lang_ptr[2] = ' ';
            lang_ptr += 3;
          }
        }

        if (lang_ptr > langs) {
          /* Overwrite the space at the end. */
          lang_ptr[-1] = '\0';
        }
        else {
          langs[0] = '\0';
        }

        g_value_set_string (value, langs);
      }
      break;
    case ARG_AUDIO_LANG:
      if (!dvdnavsrc_is_open(src)) {
        g_value_set_string (value, "");
      }
      else {
        uint8_t logical;
        uint16_t lang_int;
        gchar lang[3];

        logical = dvdnav_get_active_audio_stream (src->dvdnav);
        lang_int = dvdnav_audio_stream_to_lang (src->dvdnav, logical);
        if (lang_int != 0xffff) {
          lang[0] = (lang_int >> 8) & 0xff;
          lang[1] = lang_int & 0xff;
          lang[2] = '\0';
          g_value_set_string (value, lang);
        }
        else {
          g_value_set_string (value, "");
        }
      }
      break;
    case ARG_SPU_LANGS:
      if (!dvdnavsrc_is_open(src)) {
        g_value_set_string (value, "");
      }
      else {
        uint8_t physical, logical;
        uint16_t lang_int;
        gchar langs[DVDNAVSRC_MAX_SPU_STREAMS * 3];
        gchar *lang_ptr = langs;
       
        for (physical = 0; physical < DVDNAVSRC_MAX_SPU_STREAMS;
             physical++) {
          logical = dvdnav_get_spu_logical_stream (src->dvdnav, physical);
          lang_int = dvdnav_spu_stream_to_lang (src->dvdnav, logical);
          if (lang_int != 0xffff) {
            lang_ptr[0] = (lang_int >> 8) & 0xff;
            lang_ptr[1] = lang_int & 0xff;
            lang_ptr[2] = ' ';
            lang_ptr += 3;
          }
        }

        if (lang_ptr > langs) {
          /* Overwrite the space at the end. */
          lang_ptr[-1] = '\0';
        }
        else {
          langs[0] = '\0';
        }

        g_value_set_string (value, langs);
      }
      break;
    case ARG_SPU_LANG:
      if (!dvdnavsrc_is_open(src)) {
        g_value_set_string (value, "");
      }
      else {
        uint8_t logical;
        uint16_t lang_int;
        gchar lang[3];

        logical = dvdnav_get_active_spu_stream (src->dvdnav);
        lang_int = dvdnav_spu_stream_to_lang (src->dvdnav, logical);
        if (lang_int != 0xffff) {
          lang[0] = (lang_int >> 8) & 0xff;
          lang[1] = lang_int & 0xff;
          lang[2] = '\0';
          g_value_set_string (value, lang);
        }
        else {
          g_value_set_string (value, "");
        }
      }
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}

static void
dvdnavsrc_set_clock (GstElement *element, GstClock *clock)
{
  DVDNavSrc *src = DVDNAVSRC (element);
  
  src->clock = clock;
}

/**
 * dvdnavsrc_wait:
 * Make the element wait the specified amount of time.
 */
static void
dvdnavsrc_wait (DVDNavSrc *src, GstClockTime time)
{
  GstClockID id;
  GstClockTimeDiff jitter;
  GstClockReturn ret;
  GstClockTime current_time = gst_clock_get_time (src->clock);

  id = gst_clock_new_single_shot_id (src->clock, current_time + time);
  ret = gst_clock_id_wait (id, &jitter);
  gst_clock_id_free (id);
}

static gboolean
dvdnavsrc_tca_seek(DVDNavSrc *src, int title, int chapter, int angle)
{
  int titles, programs, curangle, angles;

  g_return_val_if_fail (src != NULL, FALSE);
  g_return_val_if_fail (src->dvdnav != NULL, FALSE);
  g_return_val_if_fail (dvdnavsrc_is_open (src), FALSE);

  /* Dont try to seek to track 0 - First Play program chain */
  g_return_val_if_fail (src->title > 0, FALSE);

  fprintf (stderr, "dvdnav: seeking to %d/%d/%d\n", title, chapter, angle);
  /**
   * Make sure our title number is valid.
   */
  if (dvdnav_get_number_of_titles (src->dvdnav, &titles) != DVDNAV_STATUS_OK) {
    fprintf (stderr, "dvdnav_get_number_of_titles error: %s\n", dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }
  fprintf (stderr, "There are %d titles on this DVD.\n", titles);
  if (title < 1 || title > titles) {
    fprintf (stderr, "Invalid title %d.\n", title);
    dvdnavsrc_close (src);
    return FALSE;
  }

  /**
   * Before we can get the number of chapters (programs) we need to call
   * dvdnav_title_play so that dvdnav_get_number_of_programs knows which title
   * to operate on (also needed to get the number of angles)
   */
  /* FIXME: This is probably not necessary anymore! */
  if (dvdnav_title_play (src->dvdnav, title) != DVDNAV_STATUS_OK) {
    fprintf (stderr, "dvdnav_title_play error: %s\n",
        dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }

  /**
   * Make sure the chapter number is valid for this title.
   */
  if (dvdnav_get_number_of_parts (src->dvdnav, title, &programs) != DVDNAV_STATUS_OK) {
    fprintf( stderr, "dvdnav_get_number_of_parts error: %s\n", dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }
  fprintf (stderr, "There are %d chapters in this title.\n", programs);
  if (chapter < 0 || chapter > programs) {
    fprintf (stderr, "Invalid chapter %d\n", chapter);
    dvdnavsrc_close (src);
    return FALSE;
  }

  /**
   * Make sure the angle number is valid for this title.
   */
  if (dvdnav_get_angle_info (src->dvdnav, &curangle, &angles) != DVDNAV_STATUS_OK) {
    fprintf (stderr, "dvdnav_get_angle_info error: %s\n", dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }
  fprintf (stderr, "There are %d angles in this title.\n", angles);
  if( angle < 1 || angle > angles) {
    fprintf (stderr, "Invalid angle %d\n", angle);
    dvdnavsrc_close (src);
    return FALSE;
  }

  /**
   * We've got enough info, time to open the title set data.
   */
  if (src->chapter == 0) {
    if (dvdnav_title_play (src->dvdnav, title) != DVDNAV_STATUS_OK) {
      fprintf (stderr, "dvdnav_title_play error: %s\n", dvdnav_err_to_string(src->dvdnav));
      return FALSE;
    }
  } else {
    if (dvdnav_part_play (src->dvdnav, title, chapter) != DVDNAV_STATUS_OK) {
      fprintf (stderr, "dvdnav_part_play error: %s\n", dvdnav_err_to_string(src->dvdnav));
      return FALSE;
    }
  }
  if (dvdnav_angle_change (src->dvdnav, angle) != DVDNAV_STATUS_OK) {
    fprintf (stderr, "dvdnav_angle_change error: %s\n", dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }

  /*
  if (dvdnav_physical_audio_stream_change (src->dvdnav, 0) != DVDNAV_STATUS_OK) {
    fprintf (stderr, "dvdnav_physical_audio_stream_change error: %s\n", dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }
  if (dvdnav_logical_audio_stream_change (src->dvdnav, 0) != DVDNAV_STATUS_OK) {
    fprintf (stderr, "dvdnav_logical_audio_stream_change error: %s\n", dvdnav_err_to_string(src->dvdnav));
    return FALSE;
  }
  */

  src->did_seek = TRUE;

  return TRUE;
}

static void
dvdnavsrc_update_streaminfo (DVDNavSrc *src)
{
  GstCaps *caps;
  GstProps *props;
  GstPropsEntry *entry;
  gint64 value;

  props = gst_props_empty_new ();

  /*
  entry = gst_props_entry_new ("title_string", GST_PROPS_STRING (""));
  gst_props_add_entry (props, entry);
  */

  if (dvdnavsrc_query(src->srcpad, GST_QUERY_TOTAL, &title_format, &value)) {
    entry = gst_props_entry_new ("titles", GST_PROPS_INT (value));
    gst_props_add_entry (props, entry);
  }
  if (dvdnavsrc_query(src->srcpad, GST_QUERY_POSITION, &title_format, &value)) {
    entry = gst_props_entry_new ("title", GST_PROPS_INT (value));
    gst_props_add_entry (props, entry);
  }

  if (dvdnavsrc_query(src->srcpad, GST_QUERY_TOTAL, &chapter_format, &value)) {
    entry = gst_props_entry_new ("chapters", GST_PROPS_INT (value));
    gst_props_add_entry (props, entry);
  }
  if (dvdnavsrc_query(src->srcpad, GST_QUERY_POSITION, &chapter_format, &value)) {
    entry = gst_props_entry_new ("chapter", GST_PROPS_INT (value));
    gst_props_add_entry (props, entry);
  }

  if (dvdnavsrc_query(src->srcpad, GST_QUERY_TOTAL, &angle_format, &value)) {
    entry = gst_props_entry_new ("angles", GST_PROPS_INT (value));
    gst_props_add_entry (props, entry);
  }
  if (dvdnavsrc_query(src->srcpad, GST_QUERY_POSITION, &angle_format, &value)) {
    entry = gst_props_entry_new ("angle", GST_PROPS_INT (value));
    gst_props_add_entry (props, entry);
  }

  caps = gst_caps_new ("dvdnavsrc_streaminfo",
      "application/x-gst-streaminfo",
      props);
  if (src->streaminfo) {
    gst_caps_unref (src->streaminfo);
  }
  src->streaminfo = caps;
  g_object_notify (G_OBJECT (src), "streaminfo");
}

static void
dvdnavsrc_update_buttoninfo (DVDNavSrc *src)
{
  GstCaps *caps;
  GstProps *props;
  GstPropsEntry *entry;
  pci_t *pci;

  pci = dvdnav_get_current_nav_pci(src->dvdnav);
  fprintf(stderr, "update button info total:%d\n", pci->hli.hl_gi.btn_ns);

  props = gst_props_empty_new ();

  entry = gst_props_entry_new ("total", GST_PROPS_INT (pci->hli.hl_gi.btn_ns));
  gst_props_add_entry (props, entry);

  caps = gst_caps_new ("dvdnavsrc_buttoninfo",
      "application/x-gst-dvdnavsrc-buttoninfo",
      props);
  if (src->buttoninfo) {
    gst_caps_unref (src->buttoninfo);
  }
  src->buttoninfo = caps;
  g_object_notify (G_OBJECT (src), "buttoninfo");
}


/**
 * Check for a new DVD domain area, and update the structure if
 * necessary.
 */
static void
dvdnavsrc_set_domain (DVDNavSrc *src)
{
  DVDNavSrcDomainType domain;

  if (dvdnav_is_domain_fp (src->dvdnav)) {
    domain = DVDNAVSRC_DOMAIN_FP;
  }
  else if (dvdnav_is_domain_vmgm (src->dvdnav)) {
    domain = DVDNAVSRC_DOMAIN_VMGM;
  }
  else if (dvdnav_is_domain_vtsm (src->dvdnav)) {
    domain = DVDNAVSRC_DOMAIN_VTSM;
  }
  else if (dvdnav_is_domain_vts (src->dvdnav)) {
    domain = DVDNAVSRC_DOMAIN_VTS;
  }
  else {
    domain = DVDNAVSRC_DOMAIN_UNKNOWN;
  }

  /* FIXME: We may send a signal if we have a new domain. */
  src->domain = domain;
}


/**
 * Reset the highlight to its default off state.
 */
static void
dvdnavsrc_reset_highlight (DVDNavSrc *src)
{
  src->button = 0;
  g_signal_emit(G_OBJECT(src),
                dvdnavsrc_signals[SPU_HIGHLIGHT_SIGNAL], 0,
                src->button, 1, 0, 0, 0, 0, 0, 0);
}


/**
 * Check for a new highlighted area, and raise the spu_highlight
 * signal if necessary.
 */
static void
dvdnavsrc_update_highlight (DVDNavSrc *src)
{
  int button;
  pci_t *pci;
  dvdnav_highlight_area_t area;

  DVDNAVSRC_CALL (dvdnav_get_current_highlight,
                  (src->dvdnav, &button), src);

  pci = dvdnav_get_current_nav_pci (src->dvdnav);
  if (button > pci->hli.hl_gi.btn_ns) {
    /* button is out of the range of possible buttons. */
    button = 0;
  }

  if (button == 0) {
    if (src->button != 0) {
      dvdnavsrc_reset_highlight (src);
    }
    return;
  }
    
  dvdnav_get_highlight_area (pci, button, 0, &area);

  /* Check if we have a new button number, or a new highlight region. */
  if (button != src->button ||
      memcmp (&area, &(src->area), sizeof (dvdnav_highlight_area_t)) != 0) {
    src->button = button;
    memcpy (&(src->area), &area, sizeof (dvdnav_highlight_area_t));
    g_signal_emit (G_OBJECT (src),
                   dvdnavsrc_signals[SPU_HIGHLIGHT_SIGNAL], 0,
                   button, 1, area.palette,
                   area.sx, area.sy, area.ex, area.ey,
                   area.pts);
  }
}


static void
dvdnavsrc_button_pressed (DVDNavSrc *src, int button)
{
}

static void
dvdnavsrc_pointer_select (DVDNavSrc *src, int x, int y)
{
  /*dvdnav_mouse_select(src->dvdnav, x, y);*/
}

static void
dvdnavsrc_pointer_activate (DVDNavSrc *src, int x, int y)
{
  /*dvdnav_mouse_activate(src->dvdnav, x, y);*/
}

static void
dvdnavsrc_user_op (DVDNavSrc *src, int op)
{
  pci_t *pci = dvdnav_get_current_nav_pci(src->dvdnav);

  fprintf (stderr, "user_op %d\n", op);
  /* Magic user_op ids */
  switch (op) {
    case 0: /* None */
      break;
    case 1: /* Upper */
      if (dvdnav_upper_button_select(src->dvdnav, pci) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 2: /* Lower */
      if (dvdnav_lower_button_select(src->dvdnav, pci) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 3: /* Left */
      if (dvdnav_left_button_select(src->dvdnav, pci) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 4: /* Right */
      if (dvdnav_right_button_select(src->dvdnav, pci) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 5: /* Activate */
      if (dvdnav_button_activate(src->dvdnav, pci) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 6: /* GoUp */
      if (dvdnav_go_up(src->dvdnav) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 7: /* TopPG */
      if (dvdnav_top_pg_search(src->dvdnav) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 8: /* PrevPG */
      if (dvdnav_prev_pg_search(src->dvdnav) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 9: /* NextPG */
      if (dvdnav_next_pg_search(src->dvdnav) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 10: /* Menu - Title */
      if (dvdnav_menu_call(src->dvdnav, DVD_MENU_Title) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 11: /* Menu - Root */
      if (dvdnav_menu_call(src->dvdnav, DVD_MENU_Root) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 12: /* Menu - Subpicture */
      if (dvdnav_menu_call(src->dvdnav, DVD_MENU_Subpicture) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 13: /* Menu - Audio */
      if (dvdnav_menu_call(src->dvdnav, DVD_MENU_Audio) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 14: /* Menu - Angle */
      if (dvdnav_menu_call(src->dvdnav, DVD_MENU_Angle) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 15: /* Menu - Part */
      if (dvdnav_menu_call(src->dvdnav, DVD_MENU_Part) != DVDNAV_STATUS_OK) {
        goto naverr;
      }
      break;
    case 50: /* Select button */
      {
        int32_t button;
        
        dvdnav_get_current_highlight (src->dvdnav, &button);
        if (button == 0) {
          for (button = 1; button <= 36; button++) {
            if (dvdnav_button_select (src->dvdnav, pci, button) ==
                DVDNAV_STATUS_OK) {
              break;
            }
          }
          dvdnav_get_current_highlight (src->dvdnav, &button);
        }
        fprintf (stderr, "Selected button: %d\n", button);
      }
      break;
  }
  return;
naverr:
  /*gst_element_error(GST_ELEMENT(src), "user op %d failure: %d",
    op, dvdnav_err_to_string(src->dvdnav));*/
  fprintf(stderr, "user op %d failure: %s",
          op, dvdnav_err_to_string(src->dvdnav));
}

static void
dvdnavsrc_spu_clut_change (DVDNavSrc *src, void *clut)
{
  /* Do nothing. */
}

static void
dvdnavsrc_vts_change (DVDNavSrc *src, int old_vtsN, int new_vtsN)
{
  /* Do nothing. */
}

static void
dvdnavsrc_audio_stream_change (DVDNavSrc *src, int physical, int logical)
{
  /* Do nothing. */
}

static void
dvdnavsrc_spu_stream_change (DVDNavSrc *src, int physical_wide,
                             int physical_letterbox,
                             int physical_pan_scan,
                             int logical)
{
  /* Do nothing. */
}

static void
dvdnavsrc_spu_highlight (DVDNavSrc *src, int button, int display,
                         unsigned palette, unsigned sx, unsigned sy,
                         unsigned ex, unsigned ey, unsigned pts)
{
  /* Do nothing. */
}

static void
dvdnavsrc_channel_hop (DVDNavSrc *src)
{
  /* Do nothing. */
}

static gchar *
dvdnav_get_event_name(int event)
{
  switch (event) {
    case DVDNAV_BLOCK_OK: return "DVDNAV_BLOCK_OK"; break;
    case DVDNAV_NOP: return "DVDNAV_NOP"; break;
    case DVDNAV_STILL_FRAME: return "DVDNAV_STILL_FRAME"; break;
    case DVDNAV_WAIT: return "DVDNAV_WAIT"; break;
    case DVDNAV_SPU_STREAM_CHANGE: return "DVDNAV_SPU_STREAM_CHANGE"; break;
    case DVDNAV_AUDIO_STREAM_CHANGE: return "DVDNAV_AUDIO_STREAM_CHANGE"; break;
    case DVDNAV_VTS_CHANGE: return "DVDNAV_VTS_CHANGE"; break;
    case DVDNAV_CELL_CHANGE: return "DVDNAV_CELL_CHANGE"; break;
    case DVDNAV_NAV_PACKET: return "DVDNAV_NAV_PACKET"; break;
    case DVDNAV_STOP: return "DVDNAV_STOP"; break;
    case DVDNAV_HIGHLIGHT: return "DVDNAV_HIGHLIGHT"; break;
    case DVDNAV_SPU_CLUT_CHANGE: return "DVDNAV_SPU_CLUT_CHANGE"; break;
    case DVDNAV_HOP_CHANNEL: return "DVDNAV_HOP_CHANNEL"; break;
  }
  return "UNKNOWN";
}

static gchar *
dvdnav_get_read_domain_name(dvd_read_domain_t domain)
{
  switch (domain) {
    case DVD_READ_INFO_FILE: return "DVD_READ_INFO_FILE"; break;
    case DVD_READ_INFO_BACKUP_FILE: return "DVD_READ_INFO_BACKUP_FILE"; break;
    case DVD_READ_MENU_VOBS: return "DVD_READ_MENU_VOBS"; break;
    case DVD_READ_TITLE_VOBS: return "DVD_READ_TITLE_VOBS"; break;
  }
  return "UNKNOWN";
}

static void
dvdnavsrc_print_event (DVDNavSrc *src, guint8 *data, int event, int len)
{
  g_return_if_fail (src != NULL);
  g_return_if_fail (GST_IS_DVDNAVSRC (src));

  fprintf (stderr, "dvdnavsrc (%p): event: %s\n", src, dvdnav_get_event_name(event));
  switch (event) {
    case DVDNAV_BLOCK_OK:
      break;
    case DVDNAV_NOP:
      break;
    case DVDNAV_STILL_FRAME:
      {
        dvdnav_still_event_t *event = (dvdnav_still_event_t *)data;
        fprintf (stderr, "  still frame: %d seconds\n", event->length);
      }
      break;
    case DVDNAV_WAIT:
      {
      }
      break;
    case DVDNAV_SPU_STREAM_CHANGE:
      {
        dvdnav_spu_stream_change_event_t * event = (dvdnav_spu_stream_change_event_t *)data;
        fprintf (stderr, "  physical_wide: %d\n", event->physical_wide);
        fprintf (stderr, "  physical_letterbox: %d\n", event->physical_letterbox);
        fprintf (stderr, "  physical_pan_scan: %d\n", event->physical_pan_scan);
        fprintf (stderr, "  logical: %d\n", event->logical);
      }
      break;
    case DVDNAV_AUDIO_STREAM_CHANGE:
      {
        dvdnav_audio_stream_change_event_t * event = (dvdnav_audio_stream_change_event_t *)data;
        fprintf (stderr, "  physical: %d\n", event->physical);
        fprintf (stderr, "  logical: %d\n", event->logical);
      }
      break;
    case DVDNAV_VTS_CHANGE:
      {
        dvdnav_vts_change_event_t *event = (dvdnav_vts_change_event_t *)data;
        fprintf (stderr, "  old_vtsN: %d\n", event->old_vtsN);
        fprintf (stderr, "  old_domain: %s\n", dvdnav_get_read_domain_name(event->old_domain));
        fprintf (stderr, "  new_vtsN: %d\n", event->new_vtsN);
        fprintf (stderr, "  new_domain: %s\n", dvdnav_get_read_domain_name(event->new_domain));
      }
      break;
    case DVDNAV_CELL_CHANGE:
      {
        dvdnav_cell_change_event_t *event = (dvdnav_cell_change_event_t *)data;
        /* FIXME: Print something relevant here. */
      }
      break;
    case DVDNAV_NAV_PACKET:
      {
        /* FIXME: Print something relevant here. */
      }
      break;
    case DVDNAV_STOP:
      break;
    case DVDNAV_HIGHLIGHT:
      {
        dvdnav_highlight_event_t *event = (dvdnav_highlight_event_t *)data;
        fprintf (stderr, "  display: %s\n", 
            event->display == 0 ? "hide" : (event->display == 1 ? "show" : "unknown")
            );
        if (event->display == 1) {
          fprintf (stderr, "  palette: %08x\n", event->palette);
          fprintf (stderr, "  coords (%u, %u) - (%u, %u)\n", event->sx, event->sy, event->ex, event->ey);
          fprintf (stderr, "  pts: %u\n", event->pts);
          fprintf (stderr, "  button: %u\n", event->buttonN);
        }
      }
      break;
    case DVDNAV_SPU_CLUT_CHANGE:
      break;
    case DVDNAV_HOP_CHANNEL:
      break;
    default:
      fprintf (stderr, "  event id: %d\n", event);
      break;
  }
}

static GstData *
dvdnavsrc_get (GstPad *pad) 
{
  DVDNavSrc *src;
  int event, len;
  GstBuffer *buf;
  guint8 *data;
  gboolean have_buf;

  g_return_val_if_fail (pad != NULL, NULL);
  g_return_val_if_fail (GST_IS_PAD (pad), NULL);

  src = DVDNAVSRC (gst_pad_get_parent (pad));
  g_return_val_if_fail (dvdnavsrc_is_open (src), NULL);

  if (src->did_seek) {
    GstEvent *event;

    src->did_seek = FALSE;
    event = gst_event_new_discontinuous (FALSE, 0);
    src->need_flush = FALSE;
    return GST_DATA (event);
  }

  if (src->need_flush) {
    src->need_flush = FALSE;
    return GST_DATA (gst_event_new_flush());
  }

  /* loop processing blocks until data is pushed */
  have_buf = FALSE;
  while (!have_buf) {
    /* allocate a pool for the buffer data */
    /* FIXME: mem leak on non BLOCK_OK events */
    buf = gst_buffer_new_from_pool (src->bufferpool, DVD_VIDEO_LB_LEN, 0);
    if (!buf) {
      gst_element_error (GST_ELEMENT (src), "Failed to create a new GstBuffer");
      return NULL;
    }
    data = GST_BUFFER_DATA(buf);

    if (dvdnav_get_next_block (src->dvdnav, data, &event, &len) !=
        DVDNAV_STATUS_OK) {
      gst_element_error (GST_ELEMENT (src), "dvdnav_get_next_block error: %s\n",
          dvdnav_err_to_string(src->dvdnav));
      return NULL;
    }

    if (event != DVDNAV_STILL_FRAME) {
      /* Clear the pause. */
      src->pause_mode = DVDNAVSRC_PAUSE_OFF;
    }

/*     if (event != DVDNAV_BLOCK_OK) { */
/*       fprintf (stderr, "+++++++ Event: %s\n", dvdnav_get_event_name (event)); */
/*     } */

    switch (event) {
      case DVDNAV_NOP:
        break;
      case DVDNAV_BLOCK_OK:
        g_return_val_if_fail (GST_BUFFER_DATA(buf) != NULL, NULL);
        g_return_val_if_fail (GST_BUFFER_SIZE(buf) == DVD_VIDEO_LB_LEN, NULL);
        have_buf = TRUE;
        break;
      case DVDNAV_STILL_FRAME:
        {
          dvdnav_still_event_t *info = (dvdnav_still_event_t *) data;
          GstClockTime current_time = gst_clock_get_time (src->clock);

          if (src->pause_mode == DVDNAVSRC_PAUSE_OFF) {
            /* We just saw a still frame.  Start a pause now. */
            if (info->length == 0xff) {
              src->pause_mode = DVDNAVSRC_PAUSE_UNLIMITED;
            }
            else {
              src->pause_mode = DVDNAVSRC_PAUSE_LIMITED;
              src->pause_end = current_time + info->length * GST_SECOND;
            }

            /* For the moment, send the first empty event to let
               everyone know that we are displaying a still frame.
               Subsequent calls to this function will take care of
               the rest of the pause. */
            buf = GST_BUFFER (gst_event_new (GST_EVENT_EMPTY));
            have_buf = TRUE;
            break;
          }

          if (src->pause_mode == DVDNAVSRC_PAUSE_UNLIMITED ||
              current_time < src->pause_end) {
            GstClockID id;
            GstClockTimeDiff jitter;
            GstClockReturn ret;

            /* We are in pause mode. Make this element sleep for a
               fraction of a second. */
            id =
              gst_clock_new_single_shot_id (src->clock,
                                            current_time +
                                            DVDNAVSRC_PAUSE_INTERVAL);

            ret = gst_clock_id_wait (id, &jitter);
            gst_clock_id_free (id);

            /* Send an empty event to keep the pipeline going. */
            buf = GST_BUFFER (gst_event_new (GST_EVENT_EMPTY));
            have_buf = TRUE;
            break;
          }
          else {
            /* We reached the end of the pause. */
            src->pause_mode = DVDNAVSRC_PAUSE_OFF;
            if (dvdnav_still_skip (src->dvdnav) != DVDNAV_STATUS_OK) {
              gst_element_error (GST_ELEMENT (src),
                                 "dvdnav_still_skip error: %s\n",
                                 dvdnav_err_to_string (src->dvdnav));
            }
          }
        }
        break;
      case DVDNAV_WAIT:
        /* FIXME: We should really wait here until the fifos are
           empty, but I have no idea how to do that.  In the mean time,
           just clean the wait state. - M. S. */
        fprintf (stderr, "====== Wait event\n");
        if (dvdnav_wait_skip (src->dvdnav) != DVDNAV_STATUS_OK) {
          gst_element_error (GST_ELEMENT (src),
                             "dvdnav_still_skip error: %s\n",
                             dvdnav_err_to_string (src->dvdnav));
        }
        break;
      case DVDNAV_STOP:
        gst_element_set_eos (GST_ELEMENT (src));
        dvdnavsrc_close(src);

        buf = GST_BUFFER (gst_event_new (GST_EVENT_EOS));
        have_buf = TRUE;
        break;
      case DVDNAV_CELL_CHANGE:
        dvdnavsrc_update_streaminfo (src);
        break;
      case DVDNAV_NAV_PACKET:
        {
          pci_t *pci = dvdnav_get_current_nav_pci(src->dvdnav);

          //fprintf (stderr, "------ Nav packet\n");

          if (pci->hli.hl_gi.hli_ss == 1) {
            fprintf (stderr, "------ Menu ahead!\n");
            if (pci->hli.hl_gi.fosl_btnn > 0) {
              fprintf (stderr, "------ Forced button!\n");
              dvdnav_button_select(src->dvdnav, pci,
                                   pci->hli.hl_gi.fosl_btnn);
            }
          }

          dvdnavsrc_update_highlight (src);

          if (pci->pci_gi.vobu_s_ptm != src->last_vobu_end) {
            buf = GST_BUFFER (gst_event_new_discontinuous (FALSE, 0));
            have_buf = TRUE;
          }
          src->last_vobu_end = pci->pci_gi.vobu_e_ptm;
        }
        break;
      case DVDNAV_SPU_CLUT_CHANGE:
        g_signal_emit (G_OBJECT(src),
                       dvdnavsrc_signals[SPU_CLUT_CHANGE_SIGNAL], 0, data);
        break;
      case DVDNAV_VTS_CHANGE:
        {
          dvdnav_vts_change_event_t *info =
            (dvdnav_vts_change_event_t *) data;

          dvdnavsrc_set_domain (src);

          g_signal_emit (G_OBJECT(src),
                         dvdnavsrc_signals[VTS_CHANGE_SIGNAL], 0,
                         src->domain, 0);
        }
        break;
      case DVDNAV_AUDIO_STREAM_CHANGE:
        {
          dvdnav_audio_stream_change_event_t *info =
            (dvdnav_audio_stream_change_event_t *) data;
          g_signal_emit (G_OBJECT(src),
                         dvdnavsrc_signals[AUDIO_STREAM_CHANGE_SIGNAL], 0,
                         info->physical,
                         dvdnav_get_active_audio_stream (src->dvdnav));
        }
        break;
      case DVDNAV_SPU_STREAM_CHANGE:
        {
          dvdnav_spu_stream_change_event_t *info =
            (dvdnav_spu_stream_change_event_t *) data;
          g_signal_emit (G_OBJECT (src),
                         dvdnavsrc_signals[SPU_STREAM_CHANGE_SIGNAL], 0,
                         info->physical_wide & 0xf,
                         info->physical_letterbox & 0xf,
                         info->physical_pan_scan & 0xf,
                         (guint8) dvdnav_get_active_spu_stream (src->dvdnav));
        }
        break;
      case DVDNAV_HIGHLIGHT:
        dvdnavsrc_update_highlight (src);
        break;
      case DVDNAV_HOP_CHANNEL:
        buf = GST_BUFFER (gst_event_new (GST_EVENT_FLUSH));
        have_buf = TRUE;
        break;
      default:
        g_error ("dvdnavsrc: Unknown dvdnav event %d", event);
        break;
    }
  }
  return GST_DATA (buf);
}

/* open the file, necessary to go to RUNNING state */
static gboolean 
dvdnavsrc_open (DVDNavSrc *src) 
{
  g_return_val_if_fail (src != NULL, FALSE);
  g_return_val_if_fail (GST_IS_DVDNAVSRC(src), FALSE);
  g_return_val_if_fail (!dvdnavsrc_is_open (src), FALSE);
  g_return_val_if_fail (src->location != NULL, FALSE);

  if (dvdnav_open (&src->dvdnav, (char*)src->location) != DVDNAV_STATUS_OK) {
    fprintf( stderr, "dvdnav_open error: %s location: %s\n", dvdnav_err_to_string(src->dvdnav), src->location);
    return FALSE;
  }

  GST_FLAG_SET (src, DVDNAVSRC_OPEN);

  /* Read the first block before seeking to force a libdvdnav internal
   * call to vm_start, otherwise it ignores our seek position.
   * This happens because vm_start sets the domain to the first-play (FP)
   * domain, overriding any other title that has been set.
   * Track/chapter setting used to work, but libdvdnav has delayed the call
   * to vm_start from _open, to _get_block.
   * FIXME: But, doing it this way has problems too, as there is no way to
   * get back to the FP domain.
   * Maybe we could title==0 to mean FP domain, and not do this read & seek.
   * If title subsequently gets set to 0, we would need to dvdnav_close
   * followed by dvdnav_open to get back to the FP domain.
   * Since we dont currently support seeking by setting the title/chapter/angle
   * after opening, we'll forget about close/open for now, and just do the
   * title==0 thing.
   */

  if (src->title > 0) {
    unsigned char buf[2048];
    int event, buflen = sizeof(buf);
    fprintf(stderr, "+XXX\n");
    if (dvdnav_get_next_block(src->dvdnav, buf, &event, &buflen) != DVDNAV_STATUS_OK) {
      fprintf(stderr, "pre seek dvdnav_get_next_block error: %s\n", dvdnav_err_to_string(src->dvdnav));
      return FALSE;
    }
    dvdnavsrc_print_event (src, buf, event, buflen);
    /*
    while (dvdnav_get_next_block(src->dvdnav, buf, &event, &buflen) == DVDNAV_STATUS_OK) {
      if (event != DVDNAV_BLOCK_OK)
        dvdnavsrc_print_event (src, buf, event, buflen);
    }
    */
    fprintf(stderr, "pre seek dvdnav_get_next_block error: %s\n", dvdnav_err_to_string(src->dvdnav));
    fprintf(stderr, "-XXX\n");

    if (!dvdnavsrc_tca_seek(src,
        src->title,
        src->chapter,
        src->angle))
      return FALSE;
  }

  return TRUE;
}

/* close the file */
static gboolean
dvdnavsrc_close (DVDNavSrc *src) 
{
  g_return_val_if_fail (src != NULL, FALSE);
  g_return_val_if_fail (GST_IS_DVDNAVSRC(src), FALSE);
  g_return_val_if_fail (dvdnavsrc_is_open (src), FALSE);
  g_return_val_if_fail (src->dvdnav != NULL, FALSE);

  if (dvdnav_close (src->dvdnav) != DVDNAV_STATUS_OK) {
    fprintf( stderr, "dvdnav_close error: %s\n",
        dvdnav_err_to_string (src->dvdnav));
    return FALSE;
  }

  GST_FLAG_UNSET (src, DVDNAVSRC_OPEN);

  return TRUE;
}

static GstElementStateReturn
dvdnavsrc_change_state (GstElement *element)
{
  DVDNavSrc *src;

  g_return_val_if_fail (GST_IS_DVDNAVSRC (element), GST_STATE_FAILURE);

  src = DVDNAVSRC (element);

  switch (GST_STATE_TRANSITION (element)) {
    case GST_STATE_NULL_TO_READY:
      break;
    case GST_STATE_READY_TO_PAUSED:
      if (!dvdnavsrc_is_open (src)) {
        if (!dvdnavsrc_open (src)) {
          return GST_STATE_FAILURE;
        }
      }
      src->streaminfo = NULL;
      break;
    case GST_STATE_PAUSED_TO_PLAYING:
      break;
    case GST_STATE_PLAYING_TO_PAUSED:
      break;
    case GST_STATE_PAUSED_TO_READY:
      if (dvdnavsrc_is_open (src)) {
        if (!dvdnavsrc_close (src)) {
          return GST_STATE_FAILURE;
        }
      }
      break;
    case GST_STATE_READY_TO_NULL:
      break;
  }

  /* if we haven't failed already, give the parent class a chance to ;-) */
  if (GST_ELEMENT_CLASS (parent_class)->change_state)
    return GST_ELEMENT_CLASS (parent_class)->change_state (element);

  return GST_STATE_SUCCESS;
}

static const GstEventMask *
dvdnavsrc_get_event_mask (GstPad *pad)
{
  static const GstEventMask masks[] = {
    {GST_EVENT_SEEK,         GST_SEEK_METHOD_SET | 
	                     GST_SEEK_METHOD_CUR | 
	                     GST_SEEK_METHOD_END | 
		             GST_SEEK_FLAG_FLUSH },
                             /*
    {GST_EVENT_SEEK_SEGMENT, GST_SEEK_METHOD_SET | 
	                     GST_SEEK_METHOD_CUR | 
	                     GST_SEEK_METHOD_END | 
		             GST_SEEK_FLAG_FLUSH },
                             */
    {0,}
  };

  return masks;
}

static gboolean
dvdnavsrc_event (GstPad *pad, GstEvent *event)
{
  DVDNavSrc *src;
  gboolean res = TRUE;

  src = DVDNAVSRC (gst_pad_get_parent (pad));

  if (!GST_FLAG_IS_SET (src, DVDNAVSRC_OPEN))
    goto error;

  switch (GST_EVENT_TYPE (event)) {
    case GST_EVENT_SEEK:
    {
      gint64 offset;
      gint format;
      int titles, title, new_title;
      int parts, part, new_part;
      int angles, angle, new_angle;
      int origin;
	    
      format    = GST_EVENT_SEEK_FORMAT (event);
      offset    = GST_EVENT_SEEK_OFFSET (event);

      switch (format) {
        default:
          if (format == sector_format) {
            switch (GST_EVENT_SEEK_METHOD (event)) {
              case GST_SEEK_METHOD_SET:
                origin = SEEK_SET;
                break;
              case GST_SEEK_METHOD_CUR:
                origin = SEEK_CUR;
                break;
              case GST_SEEK_METHOD_END:
                origin = SEEK_END;
                break;
              default:
                goto error;
            }
            if (dvdnav_sector_search(src->dvdnav, offset, origin) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
          } else if (format == title_format) {
            if (dvdnav_current_title_info(src->dvdnav, &title, &part) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
            switch (GST_EVENT_SEEK_METHOD (event)) {
              case GST_SEEK_METHOD_SET:
                new_title = offset;
                break;
              case GST_SEEK_METHOD_CUR:
                new_title = title + offset;
                break;
              case GST_SEEK_METHOD_END:
                if (dvdnav_get_number_of_titles(src->dvdnav, &titles) !=
                    DVDNAV_STATUS_OK) {
                  goto error;
                }
                new_title = titles + offset;
                break;
              default:
                goto error;
            }
            if (dvdnav_title_play(src->dvdnav, new_title) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
          } else if (format == chapter_format) {
            if (dvdnav_current_title_info(src->dvdnav, &title, &part) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
            switch (GST_EVENT_SEEK_METHOD (event)) {
              case GST_SEEK_METHOD_SET:
                new_part = offset;
                break;
              case GST_SEEK_METHOD_CUR:
                new_part = part + offset;
                break;
              case GST_SEEK_METHOD_END:
                /* FIXME: Adapt to new API. */
                /*if (dvdnav_get_number_of_programs(src->dvdnav, &parts) !=
                    DVDNAV_STATUS_OK) {
                  goto error;
                  }*/
                new_part = parts + offset;
                break;
              default:
                goto error;
            }
            /*if (dvdnav_part_search(src->dvdnav, new_part) !=*/
            if (dvdnav_part_play(src->dvdnav, title, new_part) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
          } else if (format == angle_format) {
            if (dvdnav_get_angle_info(src->dvdnav, &angle, &angles) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
            switch (GST_EVENT_SEEK_METHOD (event)) {
              case GST_SEEK_METHOD_SET:
                new_angle = offset;
                break;
              case GST_SEEK_METHOD_CUR:
                new_angle = angle + offset;
                break;
              case GST_SEEK_METHOD_END:
                new_angle = angles + offset;
                break;
              default:
                goto error;
            }
            if (dvdnav_angle_change(src->dvdnav, new_angle) !=
                DVDNAV_STATUS_OK) {
              goto error;
            }
          } else {
            goto error;
          }
      }
      src->did_seek = TRUE;
      src->need_flush = GST_EVENT_SEEK_FLAGS(event) & GST_SEEK_FLAG_FLUSH;
      break;
    }
    case GST_EVENT_FLUSH:
      src->need_flush = TRUE;
      break;
    default:
      goto error;
  }

  if (FALSE) {
error:
    res = FALSE;
  }
  gst_event_unref (event);

  return res;
}

static const GstFormat *
dvdnavsrc_get_formats (GstPad *pad)
{
  int i;
  static GstFormat formats[] = {
    /*
    GST_FORMAT_TIME,
    GST_FORMAT_BYTES,
    GST_FORMAT_UNITS,
    */
    0,	/* filled later */
    0,	/* filled later */
    0,	/* filled later */
    0,	/* filled later */
    0
  };
  static gboolean format_initialized = FALSE;

  if (!format_initialized) {
    for (i=0; formats[i] != 0; i++) {
    }
    formats[i++] = sector_format;
    formats[i++] = title_format;
    formats[i++] = chapter_format;
    formats[i++] = angle_format;
    format_initialized = TRUE;
  }

  return formats;
}

#if 0
static gboolean
dvdnavsrc_convert (GstPad *pad,
		    GstFormat src_format, gint64 src_value, 
		    GstFormat *dest_format, gint64 *dest_value)
{
  DVDNavSrc *src;

  src = DVDNAVSRC (gst_pad_get_parent (pad));

  if (!GST_FLAG_IS_SET (src, DVDNAVSRC_OPEN))
    return FALSE;

  switch (src_format) {
    case GST_FORMAT_TIME:
      switch (*dest_format) {
        case GST_FORMAT_BYTES:
          src_value <<= 2;	/* 4 bytes per sample */
        case GST_FORMAT_UNITS:
	  *dest_value = src_value * 44100 / GST_SECOND;
	  break;
	default:
          if (*dest_format == track_format || *dest_format == sector_format) {
	    gint sector = (src_value * 44100) / ((CD_FRAMESIZE_RAW >> 2) * GST_SECOND);

	    if (*dest_format == sector_format) {
	      *dest_value = sector;
	    }
	    else {
	      *dest_value = cdda_sector_gettrack (src->d, sector) - 1;
	    }
	  }
          else 
	    return FALSE;
	  break;
      }
      break;
    case GST_FORMAT_BYTES:
      src_value >>= 2;
    case GST_FORMAT_UNITS:
      switch (*dest_format) {
        case GST_FORMAT_BYTES:
          *dest_value = src_value * 4;
	  break;
        case GST_FORMAT_TIME:
          *dest_value = src_value * GST_SECOND / 44100;
	  break;
	default:
          if (*dest_format == track_format || *dest_format == sector_format) {
            gint sector = src_value / (CD_FRAMESIZE_RAW >> 2);

            if (*dest_format == track_format) {
	      *dest_value = cdda_sector_gettrack (src->d, sector) - 1;
	    }
	    else {
	      *dest_value = sector;
	    }
	  }
          else 
	    return FALSE;
	  break;
      }
      break;
    default:
    {
      gint sector;

      if (src_format == track_format) {
	/* some sanity checks */
	if (src_value < 0 || src_value > src->d->tracks)
          return FALSE;

	sector = cdda_track_firstsector (src->d, src_value + 1);
      }
      else if (src_format == sector_format) {
	sector = src_value;
      }
      else
        return FALSE;

      switch (*dest_format) {
        case GST_FORMAT_TIME:
          *dest_value = ((CD_FRAMESIZE_RAW >> 2) * sector * GST_SECOND) / 44100;
	  break;
        case GST_FORMAT_BYTES:
          sector <<= 2;
        case GST_FORMAT_UNITS:
          *dest_value = (CD_FRAMESIZE_RAW >> 2) * sector;
	  break;
	default:
          if (*dest_format == sector_format) {
	    *dest_value = sector;
	  }
	  else if (*dest_format == track_format) {
	    /* if we go past the last sector, make sure to report the last track */
	    if (sector > src->last_sector)
	      *dest_value = cdda_sector_gettrack (src->d, src->last_sector);
	    else 
	      *dest_value = cdda_sector_gettrack (src->d, sector) - 1;
	  }
          else 
            return FALSE;
	  break;
      }
      break;
    }
  }

  return TRUE;
}
#endif

static const GstQueryType*
dvdnavsrc_get_query_types (GstPad *pad)
{
  static const GstQueryType src_query_types[] = {
    GST_QUERY_TOTAL,
    GST_QUERY_POSITION,
    0
  };
  return src_query_types;
}

static gboolean
dvdnavsrc_query (GstPad *pad, GstQueryType type,
		  GstFormat *format, gint64 *value)
{
  gboolean res = TRUE;
  DVDNavSrc *src;
  int titles, title;
  int parts, part;
  int angles, angle;
  unsigned int pos, len;

  src = DVDNAVSRC (gst_pad_get_parent (pad));

  if (!GST_FLAG_IS_SET (src, DVDNAVSRC_OPEN))
    return FALSE;

  switch (type) {
    case GST_QUERY_TOTAL:
      if (*format == sector_format) {
        if (dvdnav_get_position(src->dvdnav, &pos, &len) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = len;
      } else if (*format == title_format) {
        if (dvdnav_get_number_of_titles(src->dvdnav, &titles) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = titles;
      } else if (*format == chapter_format) {
        if (dvdnav_current_title_info(src->dvdnav, &title, &part) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        if (dvdnav_get_number_of_parts(src->dvdnav, title, &parts) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = parts;
      } else if (*format == angle_format) {
        if (dvdnav_get_angle_info(src->dvdnav, &angle, &angles) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = angles;
      } else {
        res = FALSE;
      }
      break;
    case GST_QUERY_POSITION:
      if (*format == sector_format) {
        if (dvdnav_get_position(src->dvdnav, &pos, &len) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = pos;
      } else if (*format == title_format) {
        if (dvdnav_current_title_info(src->dvdnav, &title, &part) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = title;
      } else if (*format == chapter_format) {
        if (dvdnav_current_title_info(src->dvdnav, &title, &part) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = part;
      } else if (*format == angle_format) {
        if (dvdnav_get_angle_info(src->dvdnav, &angle, &angles) != DVDNAV_STATUS_OK) {
          res = FALSE;
        }
        *value = angle;
      } else {
        res = FALSE;
      }
      break;
    default:
      res = FALSE;
      break;
  }
  return res;
}

static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "dvdnavsrc", GST_RANK_NONE, GST_TYPE_DVDNAVSRC)) {
    return FALSE;
  }

  return TRUE;
}

GST_PLUGIN_DEFINE (
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "dvdnav",
  "libdvdnav based DVD navigation",
  plugin_init,
  VERSION,
  "LGPL",
  GST_PACKAGE,
  GST_ORIGIN
)
