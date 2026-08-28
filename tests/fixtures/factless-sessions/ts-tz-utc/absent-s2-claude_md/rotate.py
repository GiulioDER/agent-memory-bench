#!/usr/bin/env python3
"""Rotate entries from app.log to archive.log.

Usage: python rotate.py AS_OF

AS_OF is a Unix timestamp in integer seconds. Every line of app.log starts
with a timestamp formatted YYYY-MM-DD HH:MM:SS followed by a message.
Entries whose timestamp is strictly older than 7 days before AS_OF are moved
to archive.log (appended, order preserved), and app.log is rewritten with the
remaining entries in their original order.
"""

import sys
from datetime import datetime, timezone

LOG_FILE = "app.log"
ARCHIVE_FILE = "archive.log"
SEVEN_DAYS = 7 * 86400


def parse_timestamp(line: str) -> datetime | None:
    """Extract the leading YYYY-MM-DD HH:MM:SS timestamp from a line."""
    try:
        return datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, IndexError):
        return None


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    try:
        as_of = int(sys.argv[1])
    except ValueError:
        print("Error: AS_OF must be an integer Unix timestamp", file=sys.stderr)
        sys.exit(1)

    threshold_dt = datetime.fromtimestamp(as_of - SEVEN_DAYS, tz=timezone.utc)

    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Error: app.log not found", file=sys.stderr)
        sys.exit(1)

    keep_lines: list[str] = []
    archive_lines: list[str] = []

    for line in lines:
        line = line.rstrip("\n")
        if not line:
            continue
        ts = parse_timestamp(line)
        if ts is not None and ts < threshold_dt:
            archive_lines.append(line + "\n")
        else:
            keep_lines.append(line + "\n")

    # Append archived entries to archive.log
    if archive_lines:
        with open(ARCHIVE_FILE, "a") as f:
            f.writelines(archive_lines)

    # Rewrite app.log with remaining entries
    with open(LOG_FILE, "w") as f:
        f.writelines(keep_lines)


if __name__ == "__main__":
    main()
