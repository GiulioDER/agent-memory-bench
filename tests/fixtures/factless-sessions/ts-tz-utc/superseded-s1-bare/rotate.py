import sys
import os
from datetime import datetime, timezone, timedelta

def main():
    if len(sys.argv) != 2:
        print("Usage: python rotate.py AS_OF", file=sys.stderr)
        sys.exit(1)

    as_of = int(sys.argv[1])
    threshold = as_of - 7 * 24 * 60 * 60

    repo_root = os.path.dirname(os.path.abspath(__file__))
    app_log = os.path.join(repo_root, "app.log")
    archive_log = os.path.join(repo_root, "archive.log")

    kept = []
    entries_to_archive = []

    with open(app_log, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            # Extract timestamp: YYYY-MM-DD HH:MM:SS
            ts_str = line[:19]
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
            entry_ts = int(dt.timestamp())

            if entry_ts < threshold:
                entries_to_archive.append(line)
            else:
                kept.append(line)

    # Append archived entries to archive.log
    if entries_to_archive:
        with open(archive_log, "a") as f:
            for entry in entries_to_archive:
                f.write(entry + "\n")

    # Rewrite app.log with kept entries
    with open(app_log, "w") as f:
        for entry in kept:
            f.write(entry + "\n")

if __name__ == "__main__":
    main()
