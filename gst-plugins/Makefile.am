if HAVE_A52DEC
A52DEC_DIR=a52dec
else
A52DEC_DIR=
endif

if HAVE_ALSA
ALSASPDIF_DIR=alsaspdif
else
ALSASPDIF_DIR=
endif

SUBDIRS=$(A52DEC_DIR) $(ALSASPDIF_DIR) capspipe dvdblock iec958 \
	 mpegstream mpeg2sub queue robustclock
