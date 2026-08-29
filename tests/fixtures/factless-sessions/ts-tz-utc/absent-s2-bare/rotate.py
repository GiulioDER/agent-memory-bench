"""Rotate app.log: move entries older than 7 days before AS_OF to archive.log."""

import sys
from datetime import datetime, timezone


def parse_timestamp(line):
    """Parse the leading timestamp from a log line. Returns a datetime or None."""
    try:
        ts_str = line[:19]  # 'YYYY-MM-DD HH:MM:SS'
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def main():
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} AS_OF', file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    # 7 days before AS_OF (strictly older means older than this cutoff)
    cutoff = as_of - 7 * 24 * 60 * 60
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)

    with open('app.log', 'r') as f:
        lines = f.readlines()

    kept = []
    archived = []

    for line in lines:
        if not line.strip():
            kept.append(line)
            continue
        dt = parse_timestamp(line)
        if dt is None:
            kept.append(line)
            continue
        if dt < cutoff_dt:
            archived.append(line)
        else:
            kept.append(line)

    # Append archived entries to archive.log
    if archived:
        with open('archive.log', 'a') as f:
            f.writelines(archived)

    # Rewrite app.log with kept entries
    with open('app.log', 'w') as f:
        f.writelines(kept)


if __name__ == '__main__':
    main()
