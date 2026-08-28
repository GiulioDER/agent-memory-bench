"""Rotate old entries from app.log into archive.log."""

import sys
from datetime import datetime, timezone, timedelta


def parse_timestamp(line):
    """Extract and parse the YYYY-MM-DD HH:MM:SS prefix from a log line."""
    ts_str = line[:19]  # 'YYYY-MM-DD HH:MM:SS' is exactly 19 chars
    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff = as_of - 7 * 86400  # 7 days in seconds

    with open("app.log", "r") as f:
        lines = f.readlines()

    old_entries = []
    new_entries = []

    for line in lines:
        line = line.rstrip("\n")
        if not line:
            continue
        ts = parse_timestamp(line)
        if ts.timestamp() < cutoff:
            old_entries.append(line)
        else:
            new_entries.append(line)

    with open("archive.log", "a") as f:
        for entry in old_entries:
            f.write(entry + "\n")

    with open("app.log", "w") as f:
        for entry in new_entries:
            f.write(entry + "\n")


if __name__ == "__main__":
    main()
