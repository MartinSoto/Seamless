#!/bin/sh

# Automake
if test -z $AUTOMAKE; then 
    export AUTOMAKE=automake 
    export ACLOCAL='aclocal'
fi

# Autoheader
if test -z $AUTOHEADER; then 
    export AUTOHEADER=autoheader
fi

# Autoconf
if test -z $AUTOCONF; then
    export AUTOCONF=autoconf
fi

# Show what we do
set -x

# if any of these steps fails, the others will not execute, which is good
# we want to treat errors as soon as possible
$ACLOCAL && 
libtoolize --force && \
$AUTOHEADER
$AUTOMAKE -a && \
$AUTOCONF && \
./configure --enable-maintainer-mode
