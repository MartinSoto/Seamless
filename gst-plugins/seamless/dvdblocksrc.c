/* Seamless DVD Player
 * Copyright (C) 2005 Martin Soto <martinsoto@users.sourceforge.net>
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

#include <string.h>

#include "dvdblocksrc.h"


GST_DEBUG_CATEGORY_STATIC (dvdblocksrc_debug);
#define GST_CAT_DEFAULT (dvdblocksrc_debug)

/* The size of a DVD block. */
#define DVDBLOCKSRC_BLOCK_SIZE 2048

/* Number of 2048 byte blocks in the read buffer. */
#define DVDBLOCKSRC_MAX_BUF_SIZE 1


/* ElementFactory information. */
static GstElementDetails dvdblocksrc_details = GST_ELEMENT_DETAILS (
  "DVD block based source element",
  "Source/File/DVD",
  "Reads information from a DVD in a block oriented fashion",
  "Martin Soto <martinsoto@users.sourceforge.net>");


/* DVDBlockSrc signals and properties. */
enum {
  VOBU_READ_SIGNAL,
  VOBU_HEADER_SIGNAL,
  EVENT_SIGNAL,
  DO_SEEK_SIGNAL,
  LAST_SIGNAL,
};

enum {
  PROP_0,
  PROP_LOCATION,
  PROP_TITLE,
  PROP_DOMAIN,
  PROP_VOBU_START,
  PROP_CANCEL_VOBU,
};


static GstStaticPadTemplate dvdblocksrc_src_template =
GST_STATIC_PAD_TEMPLATE (
    "src",
    GST_PAD_SRC,
    GST_PAD_ALWAYS,
    GST_STATIC_CAPS (
        "video/mpeg, "
        "mpegversion = (int) [ 1, 2 ], "
        "systemstream = (boolean) true"
    )
);


#define _do_init(bla) \
    GST_DEBUG_CATEGORY_INIT (dvdblocksrc_debug, "dvdblocksrc", 0, \
        "DVD block reading element");

GST_BOILERPLATE_FULL (DVDBlockSrc, dvdblocksrc, GstPushSrc, GST_TYPE_PUSH_SRC,
    _do_init);

static void
dvdblocksrc_base_init(gpointer g_class);
static void
dvdblocksrc_class_init (DVDBlockSrcClass *klass);
static void
dvdblocksrc_finalize (GObject *object);

static gboolean
dvdblocksrc_stop (GstBaseSrc * bsrc);

static void
dvdblocksrc_set_property (GObject *object,
    guint prop_id, 
    const GValue *value,
    GParamSpec *pspec);
static void
dvdblocksrc_get_property (GObject *object,
    guint prop_id, 
    GValue *value,
    GParamSpec *pspec);

static gboolean
dvdblocksrc_event (GstBaseSrc * src, GstEvent * event);

static GstFlowReturn
dvdblocksrc_create (GstPushSrc * psrc, GstBuffer ** outbuf);

static void
dvdblocksrc_open_root (DVDBlockSrc *src);
static void
dvdblocksrc_close_root (DVDBlockSrc *src);
static void
dvdblocksrc_open_file (DVDBlockSrc *src);
static void
dvdblocksrc_close_file (DVDBlockSrc *src);

static gboolean
dvdblocksrc_is_seekable (GstBaseSrc *src);
static gboolean
dvdblocksrc_do_seek (GstBaseSrc *src, GstSegment *segment);


static guint dvdblocksrc_signals[LAST_SIGNAL] = { 0 };


static void
dvdblocksrc_base_init (gpointer g_class)
{
  GstElementClass *element_class = GST_ELEMENT_CLASS (g_class);
  
  gst_element_class_set_details (element_class, &dvdblocksrc_details);
  gst_element_class_add_pad_template (element_class,
      gst_static_pad_template_get (&dvdblocksrc_src_template));
}


static void
dvdblocksrc_class_init (DVDBlockSrcClass *klass) 
{
  GObjectClass *gobject_class;
  GstElementClass *gstelement_class;
  GstBaseSrcClass *gstbasesrc_class;
  GstPushSrcClass *gstpush_src_class;

  gobject_class = G_OBJECT_CLASS (klass);
  gstelement_class = GST_ELEMENT_CLASS (klass);
  gstbasesrc_class = (GstBaseSrcClass *) klass;
  gstpush_src_class = (GstPushSrcClass *) klass;

  parent_class = g_type_class_ref (GST_TYPE_PUSH_SRC);

  dvdblocksrc_signals[VOBU_READ_SIGNAL] =
    g_signal_new ("vobu-read",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST,
        G_STRUCT_OFFSET (DVDBlockSrcClass, vobu_read),
        NULL, NULL,
        g_cclosure_marshal_VOID__VOID,
        G_TYPE_NONE,
        0);
  dvdblocksrc_signals[VOBU_HEADER_SIGNAL] =
    g_signal_new ("vobu-header",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST,
        G_STRUCT_OFFSET (DVDBlockSrcClass, vobu_header),
        NULL, NULL,
        gst_marshal_VOID__BOXED,
        G_TYPE_NONE,
        1, GST_TYPE_BUFFER);
  dvdblocksrc_signals[EVENT_SIGNAL] =
    g_signal_new ("event",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST,
        G_STRUCT_OFFSET (DVDBlockSrcClass, event_signal),
        NULL, NULL,
        gst_marshal_VOID__BOXED,
        G_TYPE_NONE,
        1, GST_TYPE_EVENT);
  dvdblocksrc_signals[DO_SEEK_SIGNAL] =
    g_signal_new ("do-seek",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_RUN_LAST,
        G_STRUCT_OFFSET (DVDBlockSrcClass, do_seek),
        NULL, NULL,
        gst_marshal_VOID__BOXED,
        G_TYPE_NONE,
        1, GST_TYPE_SEGMENT);

  gobject_class->set_property = dvdblocksrc_set_property;
  gobject_class->get_property = dvdblocksrc_get_property;
  gobject_class->finalize = dvdblocksrc_finalize;

  g_object_class_install_property (gobject_class, PROP_LOCATION,
      g_param_spec_string ("location", "location",
          "Path to the location of the DVD device",
          NULL, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, PROP_TITLE,
      g_param_spec_int ("title", "title",
          "DVD title as defined by libdvdread",
          0, G_MAXINT, 0, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, PROP_DOMAIN,
      g_param_spec_int ("domain", "domain",
          "DVD domain as defined by libdvdread",
          0, G_MAXINT, 0, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, PROP_VOBU_START,
      g_param_spec_int ("vobu-start", "vobu-start",
          "Offset in 2048 byte blocks from begin of DVD "
          "file (as specified by 'title' and 'domain') to "
          "start of next VOBU to read",
          -1, G_MAXINT, -1, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, PROP_CANCEL_VOBU,
      g_param_spec_boolean ("cancel-vobu", "cancel-vobu",
          "When set to true, cancel playback of the current VOBU",
          FALSE, G_PARAM_READWRITE));

  gstbasesrc_class->stop = dvdblocksrc_stop;
  gstbasesrc_class->event = dvdblocksrc_event;
  gstbasesrc_class->is_seekable = dvdblocksrc_is_seekable;
  gstbasesrc_class->do_seek = dvdblocksrc_do_seek;

  gstpush_src_class->create = dvdblocksrc_create;
}


static void 
dvdblocksrc_init (DVDBlockSrc * src, DVDBlockSrcClass * klass)
{
  src->location = g_strdup ("/dev/dvd");
  src->title_num = 0;
  src->domain = DVD_READ_TITLE_VOBS;
  src->vobu_start = -1;

  src->block_offset = 0;
  src->block_count = 0;

  src->open_location = NULL;
  src->open_title_num = -1;
  src->open_domain = -1;

  src->reader = NULL;
  src->file = NULL;

  src->cancel_lock = g_mutex_new ();

  gst_base_src_set_format (GST_BASE_SRC (src), GST_FORMAT_TIME);
}


static void
dvdblocksrc_finalize (GObject *object)
{
  DVDBlockSrc *src = DVDBLOCKSRC (object);

  g_free (src->location);
  if (src->open_location != NULL) {
    g_free (src->open_location);
  }
}


static gboolean
dvdblocksrc_stop (GstBaseSrc * bsrc)
{
  DVDBlockSrc *src = DVDBLOCKSRC (bsrc);

  dvdblocksrc_close_file (src);
  dvdblocksrc_close_root (src);

  return TRUE;
}


static void
dvdblocksrc_set_property (GObject *object, guint prop_id,
    const GValue *value, GParamSpec *pspec)
{
  DVDBlockSrc *src = DVDBLOCKSRC (object);

  g_return_if_fail (GST_IS_DVDBLOCKSRC (object));
 
  switch (prop_id) {
    case PROP_LOCATION:
      if (src->location != NULL) {
        g_free (src->location);
      }

      if (g_value_get_string (value) == NULL) {
        src->location = g_strdup("/dev/dvd");
      } else {
        src->location = g_strdup (g_value_get_string (value));
      }
      break;
    case PROP_TITLE:
      src->title_num = g_value_get_int (value);
      break;
    case PROP_DOMAIN:
      src->domain = g_value_get_int (value);
      break;
    case PROP_VOBU_START:
      src->vobu_start = g_value_get_int (value);
      break;
    case PROP_CANCEL_VOBU:
      /* The cancel operation cannot be executed while 'create' is
	 running. */
      g_mutex_lock (src->cancel_lock);

      if (g_value_get_boolean (value)) {
	src->vobu_start = -1;
	src->block_count = 0;
      }

      g_mutex_unlock (src->cancel_lock);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static void   
dvdblocksrc_get_property (GObject *object, guint prop_id,
    GValue *value, GParamSpec *pspec)
{
  DVDBlockSrc *src;
 
  g_return_if_fail (GST_IS_DVDBLOCKSRC (object));
 
  src = DVDBLOCKSRC (object);
  
  switch (prop_id) {
    case PROP_LOCATION:
      g_value_set_string (value, src->location);
      break;
    case PROP_TITLE:
      g_value_set_int (value, src->title_num);
      break;
    case PROP_DOMAIN:
      g_value_set_int (value, src->domain);
      break;
    case PROP_VOBU_START:
      g_value_set_int (value, src->vobu_start);
      break;
    case PROP_CANCEL_VOBU:
      g_value_set_boolean (value, FALSE);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
  }
}


static gboolean
dvdblocksrc_event (GstBaseSrc * src, GstEvent * event)
{
  if (GST_BASE_SRC_CLASS (parent_class)->event) {
    g_signal_emit (G_OBJECT (src),
        dvdblocksrc_signals[EVENT_SIGNAL], 0, event);
    return GST_BASE_SRC_CLASS (parent_class)->event (src, event);
  } else {
    return FALSE;
  }
}


/* Try to read block_count blocks from the current file, in a newly
   allocated buffer. It could potentally read less blocks than
   requested. The size of the resulting buffer will always be set
   accordingly. */
static GstBuffer *
dvdblocksrc_read (DVDBlockSrc * src, int block_count)
{
  GstBuffer *buf;
  int blocks_read;

  buf = gst_buffer_new_and_alloc (block_count * DVDBLOCKSRC_BLOCK_SIZE);

  dvdblocksrc_open_file (src);
  blocks_read = DVDReadBlocks (src->file, src->block_offset, block_count,
      GST_BUFFER_DATA (buf));
  if (blocks_read == -1) {
    GST_ELEMENT_ERROR (src, RESOURCE, READ,
        ("Cannot read blocks, title %d, domain %d"
         ", offset %d, count %d", src->title_num,
         src->domain, src->block_offset, block_count),
        NULL);
    gst_buffer_unref (buf);
    return NULL;
  }
  GST_BUFFER_SIZE (buf) = blocks_read * DVDBLOCKSRC_BLOCK_SIZE;

  src->block_count -= blocks_read;
  src->block_offset += blocks_read;

  return buf;
}


static GstFlowReturn
dvdblocksrc_create (GstPushSrc * psrc, GstBuffer ** outbuf)
{
  DVDBlockSrc *src = DVDBLOCKSRC (psrc);
  GstBuffer *buf = NULL;
  int block_count;
  GstFlowReturn res = GST_FLOW_OK;

  GST_LOG_OBJECT (src, "entering create");

  g_mutex_lock (src->cancel_lock);

  if (src->block_count == 0 && src->vobu_start == -1) {
    /* No more work to do. */

    /* Fire the vobu_read signal to give the application a chance
       to give us more work. */
    g_signal_emit (G_OBJECT (src),
        dvdblocksrc_signals[VOBU_READ_SIGNAL], 0);

    if (src->vobu_start == -1) {
      /* We didn't get any more work, tell the base class to send an
	 EOS. */
      GST_DEBUG_OBJECT (psrc, "Sending EOS");

      res = GST_FLOW_UNEXPECTED;
      goto done;
    }
  }

  if (src->vobu_start != -1) {
    static guchar pci_header[] = {0x00, 0x00, 0x01, 0xbf, 0x03, 0xd4, 0x00};

    /* Start reading a new VOBU. */
    src->block_offset = src->vobu_start;
    src->vobu_start = -1;

    /* Read the VOBU header. */
    buf = dvdblocksrc_read (src, 1);

    /* Make sure we have a VOBU header. */
    if (memcmp (pci_header, GST_BUFFER_DATA (buf) + 0x26, sizeof pci_header)
        != 0) {
      GST_ELEMENT_ERROR (src, STREAM, FORMAT,
          ("Block, title %d, domain %d, offset %d is not a VOBU header",
           src->title_num, src->domain, src->block_offset - 1),
          NULL);
      res = GST_FLOW_ERROR;
      goto done;
    }

    /* Set the number of blocks to read. */
    src->block_count =
      GUINT32_FROM_BE (*((guint32 *) (GST_BUFFER_DATA (buf) + 0x40f)));
    GST_DEBUG_OBJECT (src, "reading new VOBU, size %d blocks",
        src->block_count + 1);

    /* Pass the header to the application. */
    g_signal_emit (G_OBJECT (src),
        dvdblocksrc_signals[VOBU_HEADER_SIGNAL], 0, buf);
  } else {
    /* Determine the size of the new buffer. */
    if (src->block_count > DVDBLOCKSRC_MAX_BUF_SIZE) {
      block_count = DVDBLOCKSRC_MAX_BUF_SIZE;
    } else {
      block_count = src->block_count;
    }

    buf = dvdblocksrc_read (src, block_count);
  }

  *outbuf = buf;

  GST_LOG_OBJECT (src, "leaving create normally, buf: %p, size: %d, data: %p",
      buf, GST_BUFFER_SIZE (buf), GST_BUFFER_DATA (buf));

 done:
  g_mutex_unlock (src->cancel_lock);
  return res;
}


static void
dvdblocksrc_open_root (DVDBlockSrc *src)
{
  if (src->open_location != NULL &&
      strcmp(src->location, src->open_location) == 0) {
    /* Location is already open.  Do nothing. */
    return;
  }

  if (src->reader != NULL) {
    dvdblocksrc_close_root (src);
  }

  src->reader = DVDOpen (src->location);
  if (src->reader == NULL) {
    GST_ELEMENT_ERROR (src, RESOURCE, OPEN_READ,
        ("Couldn't open DVD location %s", src->location),
        NULL);
    return;
  }

  src->open_location = g_strdup(src->location);
}


static void
dvdblocksrc_close_root (DVDBlockSrc *src)
{
  if (src->reader == NULL) {
    return;
  }

  DVDClose (src->reader);

  src->reader = NULL;
  g_free (src->open_location);
  src->open_location = NULL;
}


static void
dvdblocksrc_open_file (DVDBlockSrc *src)
{
  dvdblocksrc_open_root (src);

  g_return_if_fail (src->reader != NULL);

  if (src->title_num == src->open_title_num &&
      src->domain == src->open_domain) {
    /* File is not changed.  Do nothing. */
    return;
  }

  if (src->file != NULL) {
    dvdblocksrc_close_file (src);
  }

  src->file = DVDOpenFile (src->reader, src->title_num, src->domain);
  if (src->file == NULL) {
    GST_ELEMENT_ERROR (src, RESOURCE, READ,
        ("Couldn't open title %d, domain %d\n",
            src->title_num, src->domain),
        NULL);
    return;
  }

  src->open_title_num = src->title_num;
  src->open_domain = src->domain;
}


static void
dvdblocksrc_close_file (DVDBlockSrc *src)
{
  if (src->file == NULL) {
    return;
  }

  DVDCloseFile (src->file);

  src->file = NULL;
  src->open_title_num = -1;
  src->open_domain = -1;
}


static gboolean
dvdblocksrc_is_seekable (GstBaseSrc *src)
{
  return TRUE;
}


static gboolean
dvdblocksrc_do_seek (GstBaseSrc *bsrc, GstSegment *segment)
{
  DVDBlockSrc *src = DVDBLOCKSRC (bsrc);

  GST_DEBUG_OBJECT (src, "doing seek");

  /* Cancel playback of the current VOBU. */
  g_mutex_lock (src->cancel_lock);
  src->vobu_start = -1;
  src->block_count = 0;
  g_mutex_unlock (src->cancel_lock);

  g_signal_emit (G_OBJECT (src),
        dvdblocksrc_signals[DO_SEEK_SIGNAL], 0, segment);

  return TRUE;
}

