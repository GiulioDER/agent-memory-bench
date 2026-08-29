import sys
from datetime import datetime, timezone, timedelta


def main():
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    cutoff = as_of - 7 * 24 * 60 * 60  # 7 days in seconds

    with open("app.log") as f:
        lines = f.readlines()

    archive_lines = []
    keep_lines = []

    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        # Parse leading timestamp "YYYY-MM-DD HH:MM:SS"
        ts_str = line[:19]
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        entry_ts = int(dt.timestamp())

        if entry_ts < cutoff:
            archive_lines.append(line)
        else:
            keep_lines.append(line)

    # Append to archive.log
    with open("archive.log", "a") as f:
        for line in archive_lines:
            f.write(line + "\n")

    # Rewrite app.log
    with open("app.log", "w") as f:
        for line in keep_lines:
            f.write(line + "\n")


if __name__ == "__main__":
    main()