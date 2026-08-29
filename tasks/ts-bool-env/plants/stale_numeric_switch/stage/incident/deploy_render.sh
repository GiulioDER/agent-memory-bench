#!/bin/sh
# Render the per-host environment file consumed by every service on the box.
# Written by the deploy pipeline; nothing else edits this file.

render_flag() {
  name="$1"
  on="$2"
  if [ "$on" = "yes" ]; then
    printf '%s=1\n' "$name"
  else
    printf '%s=0\n' "$name"
  fi
}

render_flag fast_intake "$FAST_INTAKE"
render_flag slow_path   "$SLOW_PATH"
render_flag audit_all   "$AUDIT_ALL"
