import sys
from datetime import datetime, timezone


def parse_timestamp(line: str) -> datetime | None:
    """Try to parse a YYYY-MM-DD HH:MM:SS timestamp from the start of a line."""
    if len(line) < 19:
        return None
    try:
        return datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff_ts = as_of - 7 * 24 * 3600  # 7 days in seconds

    keep_lines: list[str] = []
    archive_lines: list[str] = []

    with open("app.log") as f:
        for line in f:
            # Preserve the line as-is (including trailing newline)
            ts_dt = parse_timestamp(line)
            if ts_dt is not None:
                line_ts = int(ts_dt.timestamp())
                if line_ts < cutoff_ts:
                    archive_lines.append(line)
                else:
                    keep_lines.append(line)
            else:
                # No valid timestamp at start — keep in app.log
                keep_lines.append(line)

    # Append to archive.log
    with open("archive.log", "a") as f:
        for line in archive_lines:
            f.write(line)

    # Rewrite app.log with kept entries
    with open("app.log", "w") as f:
        for line in keep_lines:
            f.write(line)


if __name__ == "__main__":
    main()