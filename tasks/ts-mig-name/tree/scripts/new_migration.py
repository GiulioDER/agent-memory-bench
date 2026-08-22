"""Stamp out the next migration file: python scripts/new_migration.py <slug>."""

import re
import sys
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
MAX_NAME = 30


def main() -> None:
    slug = re.sub(r"[^a-z0-9]+", "_", sys.argv[1].lower()).strip("_")
    numbers = [int(path.name[:4]) for path in MIGRATIONS.glob("[0-9]*.sql")]
    name = f"{max(numbers, default=0) + 1:04d}_{slug}.sql"
    if len(name) > MAX_NAME:
        name = name[: MAX_NAME - 4].rstrip("_") + ".sql"
    path = MIGRATIONS / name
    path.write_text("-- TODO\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
