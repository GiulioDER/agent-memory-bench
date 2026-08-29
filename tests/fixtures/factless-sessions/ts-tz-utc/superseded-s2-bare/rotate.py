#!/usr/bin/env python3
"""Rotate app.log entries older than 7 days before AS_OF into archive.log."""

import sys
import os
from datetime import datetime, timezone, timedelta


def main():
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff_dt = datetime.fromtimestamp(as_of, tz=timezone.utc) - timedelta(days=7)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_log = os.path.join(script_dir, "app.log")
    archive_log = os.path.join(script_dir, "archive.log")

    if not os.path.exists(app_log):
        print("app.log not found", file=sys.stderr)
        sys.exit(1)

    keep_lines = []
    archive_lines = []

    with open(app_log, "r") as f:
        for line in f:
            line_orig = line
            line_stripped = line.rstrip("\n")
            if not line_stripped:
                continue
            # Parse timestamp: YYYY-MM-DD HH:MM:SS
            ts_str = line_stripped[:19]
            try:
                line_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except ValueError:
                # If timestamp is unparseable, keep in app.log
                keep_lines.append(line_orig)
                continue

            if line_dt < cutoff_dt:
                archive_lines.append(line_orig)
            else:
                keep_lines.append(line_orig)

    # Append to archive.log
    with open(archive_log, "a") as f:
        for line in archive_lines:
            f.write(line)

    # Rewrite app.log
    with open(app_log, "w") as f:
        for line in keep_lines:
            f.write(line)


if __name__ == "__main__":
    main()
