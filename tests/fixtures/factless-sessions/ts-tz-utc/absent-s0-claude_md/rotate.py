#!/usr/bin/env python3
"""Rotate entries from app.log into archive.log.

Usage: python rotate.py AS_OF

Every line of app.log starts with a timestamp YYYY-MM-DD HH:MM:SS (interpreted
as UTC) followed by a message. Entries strictly older than 7 days before AS_OF
(a Unix timestamp in integer seconds) are appended to archive.log; app.log is
rewritten with the remaining entries, preserving original order.
"""

import sys
from datetime import datetime, timedelta, timezone

DATE_FMT = "%Y-%m-%d %H:%M:%S"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        return 1

    try:
        as_of = int(sys.argv[1])
    except ValueError:
        print("AS_OF must be an integer Unix timestamp", file=sys.stderr)
        return 1

    as_of_dt = datetime.fromtimestamp(as_of, tz=timezone.utc)
    cutoff = as_of_dt - timedelta(days=7)

    with open("app.log", "r", encoding="utf-8") as f:
        lines = f.readlines()

    archive_lines = []
    keep_lines = []

    for line in lines:
        ts_str = line[:19]
        ts = datetime.strptime(ts_str, DATE_FMT).replace(tzinfo=timezone.utc)
        if ts < cutoff:
            archive_lines.append(line)
        else:
            keep_lines.append(line)

    with open("archive.log", "a", encoding="utf-8") as f:
        f.writelines(archive_lines)

    with open("app.log", "w", encoding="utf-8") as f:
        f.writelines(keep_lines)

    return 0


if __name__ == "__main__":
    sys.exit(main())
