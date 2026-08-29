#!/usr/bin/env python3
"""Rotate old entries from app.log to archive.log."""

import sys
import time
import calendar


def parse_timestamp(line):
    """Extract Unix timestamp from a log line with format 'YYYY-MM-DD HH:MM:SS'."""
    ts_str = line[:19]
    return calendar.timegm(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))


def main():
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff = as_of - 7 * 24 * 60 * 60  # 7 days in seconds

    with open("app.log", "r") as f:
        lines = f.readlines()

    keep = []
    archive = []

    for line in lines:
        line_stripped = line.rstrip("\n")
        if not line_stripped:
            keep.append(line)
            continue
        try:
            ts = parse_timestamp(line_stripped)
        except (ValueError, IndexError):
            keep.append(line)
            continue

        if ts < cutoff:
            archive.append(line)
        else:
            keep.append(line)

    with open("app.log", "w") as f:
        f.writelines(keep)

    if archive:
        with open("archive.log", "a") as f:
            f.writelines(archive)


if __name__ == "__main__":
    main()
