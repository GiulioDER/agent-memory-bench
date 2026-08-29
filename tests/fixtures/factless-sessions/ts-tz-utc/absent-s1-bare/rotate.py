import sys
from datetime import datetime, timezone, timedelta


def parse_timestamp(line: str):
    """Parse YYYY-MM-DD HH:MM:SS prefix from a line, return datetime or None."""
    if len(line) < 19:
        return None
    try:
        return datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff_dt = datetime.fromtimestamp(as_of, tz=timezone.utc) - timedelta(days=7)
    cutoff_ts = cutoff_dt.timestamp()

    with open("app.log", "r") as f:
        lines = f.readlines()

    kept = []
    archived = []

    for line in lines:
        # Preserve original line content (don't strip newlines)
        dt = parse_timestamp(line)
        if dt is not None and dt.timestamp() < cutoff_ts:
            archived.append(line)
        else:
            kept.append(line)

    with open("archive.log", "a") as f:
        f.writelines(archived)

    with open("app.log", "w") as f:
        f.writelines(kept)


if __name__ == "__main__":
    main()