#!/bin/sh
# Read one flag out of config.ini. Written 2019, unchanged since.
v=$(sed -n "s/^$1 *= *//p" config.ini | tr -d ' ')
if [ "$v" = 1 ] || [ "$v" = yes ]; then
  exit 0
fi
exit 1
