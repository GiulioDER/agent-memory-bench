"""Rotate app.log entries older than 7 days before AS_OF into archive.log."""

import sys
from datetime import datetime, timezone


def parse_timestamp(line: str) -> int:
    """Parse 'YYYY-MM-DD HH:MM:SS' at start of line into a Unix timestamp."""
    ts_str = line[:19]
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff = as_of - 7 * 86400  # 7 days in seconds

    try:
        with open("app.log") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("app.log not found", file=sys.stderr)
        sys.exit(1)

    keep = []
    archive = []

    for line in lines:
        line_stripped = line.rstrip("\n")
        if not line_stripped:
            continue
        try:
            ts = parse_timestamp(line_stripped)
        except (ValueError, IndexError):
            # lines that don't parse stay in app.log
            keep.append(line)
            continue

        if ts < cutoff:
            archive.append(line)
        else:
            keep.append(line)

    # Append archived entries to archive.log (preserving order)
    with open("archive.log", "a") as f:
        f.writelines(archive)

    # Rewrite app.log with remaining entries
    with open("app.log", "w") as f:
        f.writelines(keep)


if __name__ == "__main__":
    main()
