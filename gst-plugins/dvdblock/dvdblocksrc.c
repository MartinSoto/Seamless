/* Seamless DVD Player
 * Copyright (C) 2004 Martin Soto <martinsoto@users.sourceforge.net>
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
#define DVDBLOCKSRC_MAX_BUF_SIZE 16


/* ElementFactory information. */
static GstElementDetails dvdblocksrc_details = {
  "DVD block based source element",
  "Source/File/DVD",
  "Reads information from a DVD in a block oriented fashion",
  "Martin Soto <martinsoto@users.sourceforge.net>"
};


/* DVDBlockSrc signals and args */
enum {
  VOBU_READ_SIGNAL,
  VOBU_HEADER_SIGNAL,
  QUEUE_EVENT_SIGNAL,
  LAST_SIGNAL,
};

enum {
  ARG_0,
  ARG_LOCATION,
  ARG_TITLE,
  ARG_DOMAIN,
  ARG_VOBU_START,
  ARG_BLOCK_COUNT,
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


static void
dvdblocksrc_base_init(gpointer g_class);
static void
dvdblocksrc_class_init (DVDBlockSrcClass *klass);
static void
dvdblocksrc_init (DVDBlockSrc *ac3iec);
static void
dvdblocksrc_finalize (GObject *object);

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

static void
dvdblocksrc_loop (GstElement *element);

static GstElementStateReturn
dvdblocksrc_change_state (GstElement *element);

static void
dvdblocksrc_open_root (DVDBlockSrc *src);
static void
dvdblocksrc_close_root (DVDBlockSrc *src);
static void
dvdblocksrc_open_file (DVDBlockSrc *src);
static void
dvdblocksrc_close_file (DVDBlockSrc *src);

static void
dvdblocksrc_queue_event (DVDBlockSrc * src, GstEvent * event);


static GstElementClass *parent_class = NULL;
static guint dvdblocksrc_signals[LAST_SIGNAL] = { 0 };


GType
dvdblocksrc_get_type (void) 
{
  static GType dvdblocksrc_type = 0;

  if (!dvdblocksrc_type) {
    static const GTypeInfo dvdblocksrc_info = {
      sizeof (DVDBlockSrcClass),
      dvdblocksrc_base_init,
      NULL,
      (GClassInitFunc)dvdblocksrc_class_init,
      NULL,
      NULL,
      sizeof (DVDBlockSrc),
      0,
      (GInstanceInitFunc)dvdblocksrc_init,
    };
    dvdblocksrc_type = g_type_register_static (GST_TYPE_ELEMENT,
        "DVDBlockSrc",
        &dvdblocksrc_info, 0);

    GST_DEBUG_CATEGORY_INIT (dvdblocksrc_debug, "dvdblocksrc", 0,
        "DVD block reading element");
  }
  return dvdblocksrc_type;
}


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

  gobject_class = (GObjectClass*)klass;
  gstelement_class = (GstElementClass*)klass;

  parent_class = g_type_class_ref (GST_TYPE_ELEMENT);

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
        gst_marshal_VOID__POINTER,
        G_TYPE_NONE,
        1, GST_TYPE_BUFFER);
  dvdblocksrc_signals[QUEUE_EVENT_SIGNAL] =
    g_signal_new ("queue-event",
        G_TYPE_FROM_CLASS (klass),
        G_SIGNAL_ACTION,
        G_STRUCT_OFFSET (DVDBlockSrcClass, queue_event),
        NULL, NULL,
        gst_marshal_VOID__POINTER,
        G_TYPE_NONE,
        1, GST_TYPE_EVENT);

  g_object_class_install_property (gobject_class, ARG_LOCATION,
      g_param_spec_string ("location", "location",
          "Path to the location of the DVD device",
          NULL, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, ARG_TITLE,
      g_param_spec_int ("title", "title",
          "DVD title as defined by libdvdread",
          0, G_MAXINT, 0, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, ARG_DOMAIN,
      g_param_spec_int ("domain", "domain",
          "DVD domain as defined by libdvdread",
          0, G_MAXINT, 0, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, ARG_VOBU_START,
      g_param_spec_int ("vobu-start", "vobu-start",
          "Offset in 2048 byte blocks from begin of DVD "
          "file (as specified by 'title' and 'domain') to "
          "start of next VOBU to read",
          -1, G_MAXINT, -1, G_PARAM_READWRITE));
  g_object_class_install_property (gobject_class, ARG_BLOCK_COUNT,
      g_param_spec_int ("block-count", "block-count",
          "Number of blocks still to read in this VOBU",
          0, G_MAXINT, 0, G_PARAM_READWRITE));

  gobject_class->set_property = dvdblocksrc_set_property;
  gobject_class->get_property = dvdblocksrc_get_property;
  gobject_class->finalize = dvdblocksrc_finalize;

  gstelement_class->change_state = dvdblocksrc_change_state;

  klass->queue_event = dvdblocksrc_queue_event;
}


static void 
dvdblocksrc_init (DVDBlockSrc *src)
{
  src->src = gst_pad_new_from_template (
      gst_static_pad_template_get (&dvdblocksrc_src_template),
      "src");
  gst_element_add_pad (GST_ELEMENT (src), src->src);

  gst_element_set_loop_function (GST_ELEMENT(src),
      dvdblocksrc_loop);

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

  src->event_queue = g_async_queue_new ();
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


static void
dvdblocksrc_set_property (GObject *object, guint prop_id,
    const GValue *value, GParamSpec *pspec)
{
  DVDBlockSrc *src = DVDBLOCKSRC (object);

  g_return_if_fail (GST_IS_DVDBLOCKSRC (object));
 
  switch (prop_id) {
    case ARG_LOCATION:
      if (src->location != NULL) {
        g_free (src->location);
      }

      if (g_value_get_string (value) == NULL) {
        src->location = g_strdup("/dev/dvd");
      } else {
        src->location = g_strdup (g_value_get_string (value));
      }
      break;
    case ARG_TITLE:
      src->title_num = g_value_get_int (value);
      break;
    case ARG_DOMAIN:
      src->domain = g_value_get_int (value);
      break;
    case ARG_VOBU_START:
      src->vobu_start = g_value_get_int (value);
      break;
    case ARG_BLOCK_COUNT:
      src->block_count = g_value_get_int (value);
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
    case ARG_LOCATION:
      g_value_set_string (value, src->location);
      break;
    case ARG_TITLE:
      g_value_set_int (value, src->title_num);
      break;
    case ARG_DOMAIN:
      g_value_set_int (value, src->domain);
      break;
    case ARG_VOBU_START:
      g_value_set_int (value, src->vobu_start);
      break;
    case ARG_BLOCK_COUNT:
      g_value_set_int (value, src->block_count);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, prop_id, pspec);
      break;
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


static void
dvdblocksrc_loop (GstElement *element)
{
  DVDBlockSrc *src = DVDBLOCKSRC(element);
  GstBuffer *buf;
  int block_count;
  GstEvent *event;

  /* Send any queued events. */
  event = g_async_queue_try_pop (src->event_queue);
  while (event) {
    gst_pad_push (src->src, GST_DATA (event));
    event = g_async_queue_try_pop (src->event_queue);
  }

  if (src->block_count == 0 && src->vobu_start == -1) {
    /* No more work to do. */

    /* Fire the vobu_read signal to give the application a chance
       to give us more work. */
    g_signal_emit (G_OBJECT (src),
        dvdblocksrc_signals[VOBU_READ_SIGNAL], 0);

    if (src->vobu_start == -1) {
      /* We didn't get any more work. */
      return;
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
      return;
    }

    /* Set the number of blocks to read. */
    src->block_count =
      GUINT32_FROM_BE (*((guint32 *) (GST_BUFFER_DATA (buf) + 0x40f)));
    GST_DEBUG_OBJECT (src, "reading new VOBU, size %d blocks",
        src->block_count + 1);

    /* Pass the header to the application. */
    g_signal_emit (G_OBJECT (src),
        dvdblocksrc_signals[VOBU_HEADER_SIGNAL], 0, buf);

    gst_pad_push (src->src, GST_DATA (buf));
  }

  /* Some VOBUs contain only the header. src->block_count could be 0
     here. */
  if (src->block_count > 0) {
    /* Determine the size of the new buffer. */
    if (src->block_count > DVDBLOCKSRC_MAX_BUF_SIZE) {
      block_count = DVDBLOCKSRC_MAX_BUF_SIZE;
    } else {
      block_count = src->block_count;
    }

    buf = dvdblocksrc_read (src, block_count);

    gst_pad_push (src->src, GST_DATA (buf));
  }
}


static GstElementStateReturn
dvdblocksrc_change_state (GstElement *element)
{
  DVDBlockSrc *src;

  g_return_val_if_fail (GST_IS_DVDBLOCKSRC (element), GST_STATE_FAILURE);

  src = DVDBLOCKSRC(element);

  switch (GST_STATE_TRANSITION (element)) {
    case GST_STATE_NULL_TO_READY:
      break;
    case GST_STATE_READY_TO_PAUSED:
      break;
    case GST_STATE_PAUSED_TO_PLAYING:
      break;
    case GST_STATE_PLAYING_TO_PAUSED:
      break;
    case GST_STATE_PAUSED_TO_READY:
      break;
    case GST_STATE_READY_TO_NULL:
      dvdblocksrc_close_file (src);
      dvdblocksrc_close_root (src);
      break;
  }

  if (GST_ELEMENT_CLASS (parent_class)->change_state) {
    return GST_ELEMENT_CLASS (parent_class)->change_state (element);
  }

  return GST_STATE_SUCCESS;
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


static void
dvdblocksrc_queue_event (DVDBlockSrc * src, GstEvent * event)
{
  g_async_queue_push (src->event_queue, event);
}


static gboolean
plugin_init (GstPlugin *plugin)
{
  if (!gst_element_register (plugin, "dvdblocksrc", GST_RANK_NONE,
          GST_TYPE_DVDBLOCKSRC)) {
    return FALSE;
  }

  return TRUE;
}


GST_PLUGIN_DEFINE (
  GST_VERSION_MAJOR,
  GST_VERSION_MINOR,
  "dvdblock",
  "Block based DVD reader based on libdvdread",
  plugin_init,
  VERSION,
  "GPL",
  PACKAGE,
  "http://seamless.sourceforge.net");
