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

#ifndef __DVDBLOCKSRC_H__
#define __DVDBLOCKSRC_H__

#include <glib.h>

#include <gst/gst.h>

#include <dvdread/dvd_reader.h>


G_BEGIN_DECLS


#define GST_TYPE_DVDBLOCKSRC \
  (dvdblocksrc_get_type())
#define DVDBLOCKSRC(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_DVDBLOCKSRC,DVDBlockSrc))
#define DVDBLOCKSRC_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_DVDBLOCKSRC,DVDBlockSrcClass))
#define GST_IS_DVDBLOCKSRC(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_DVDBLOCKSRC))
#define GST_IS_DVDBLOCKSRC_CLASS(obj) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_DVDBLOCKSRC))
#define GST_TYPE_DVDBLOCKSRC (dvdblocksrc_get_type())


typedef struct _DVDBlockSrc DVDBlockSrc;
typedef struct _DVDBlockSrcClass DVDBlockSrcClass;


typedef enum {
  DVDBLOCKSRC_OPEN = GST_ELEMENT_FLAG_LAST,
  DVDBLOCKSRC_FLAG_LAST
} DVDBlockSrcFlags;


struct _DVDBlockSrc {
  GstElement element;

  gchar *location;	/* Path to the DVD location. */
  int title_num;	/* Title number as in libdvdread */
  dvd_read_domain_t domain;
  			/* Domain type as in libdvdread. */
  int vobu_start;	/* Start offset of the next VOBU to read
                           (in 2048 byte blocks from file start). */

  int block_offset;	/* Current reading offset (in 2048 byte blocks
                           from file start). */
  int block_count;	/* Number of blocks yet to read. */

  gchar *open_location;	/* Path to the currently opened DVD location. */
  int open_title_num;	/* Title number of the currently opened file. */
  dvd_read_domain_t open_domain;
  			/* Domain type of the currently opened file. */

  dvd_reader_t *reader;	/* The current DVD reader object. */
  dvd_file_t *file;	/* The current DVD file object. */

  GstPad *src;		/* The source pad. */

  GAsyncQueue *event_queue;
  			/* Queue of pending events. */
};


struct _DVDBlockSrcClass {
  GstElementClass parent_class;

  /* Signals */
  void (*vobu_read)		(DVDBlockSrc * src);
  void (*vobu_header)		(DVDBlockSrc * src, GstBuffer * header);
  void (*queue_event)		(DVDBlockSrc * src, GstEvent * event);
};


extern GType	dvdblocksrc_get_type		(void);

G_END_DECLS

#endif /* __DVDBLOCKSRC__ */
