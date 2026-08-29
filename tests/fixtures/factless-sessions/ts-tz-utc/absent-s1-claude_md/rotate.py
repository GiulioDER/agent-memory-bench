"""Rotate old entries from app.log into archive.log."""

import sys
import os
from datetime import datetime, timezone, timedelta


def main():
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff = as_of - 7 * 24 * 3600  # strictly older than 7 days before AS_OF

    repo_root = os.path.dirname(os.path.abspath(__file__))
    app_log = os.path.join(repo_root, "app.log")
    archive_log = os.path.join(repo_root, "archive.log")

    # Read all entries from app.log
    with open(app_log, "r") as f:
        lines = f.readlines()

    # Separate old and new entries, preserving order
    old_entries = []
    keep_entries = []

    for line in lines:
        stripped = line.rstrip("\n")
        if not stripped:
            keep_entries.append(line)
            continue
        try:
            ts_str = stripped[:19]  # "YYYY-MM-DD HH:MM:SS"
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
            entry_ts = int(dt.timestamp())
        except (ValueError, IndexError):
            keep_entries.append(line)
            continue

        if entry_ts < cutoff:
            old_entries.append(line)
        else:
            keep_entries.append(line)

    # Append old entries to archive.log (preserving order)
    if old_entries:
        with open(archive_log, "a") as f:
            f.writelines(old_entries)

    # Rewrite app.log with kept entries
    with open(app_log, "w") as f:
        f.writelines(keep_entries)


if __name__ == "__main__":
    main()
