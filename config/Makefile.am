pypkgdir = $(pkglibdir)/python

dist_noinst_DATA = config.py.tmpl seamless.tmpl

bin_SCRIPTS = seamless

pypkg_PYTHON = config.py

config.py: config.py.tmpl
	sed -e "s,__libdir__,${libdir},g" \
	    -e "s,__PACKAGE__,${PACKAGE},g" \
	    config.py.tmpl > config.py

seamless: seamless.tmpl
	sed -e "s,__libdir__,${libdir},g" \
	    -e "s,__PACKAGE__,${PACKAGE},g" \
	    -e "s,__PYTHON__,${PYTHON},g" \
	    seamless.tmpl > seamless

CLEANFILES = config.py seamless
