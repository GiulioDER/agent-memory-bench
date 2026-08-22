"""Oracle driver: two long resource ids that must not share a cache entry."""

import json
from pathlib import Path

from fetch import fetch

NORTH = "reports/2026-07-north"
SOUTH = "reports/2026-07-south"

first_north = fetch(NORTH)
south = fetch(SOUTH)
second_north = fetch(NORTH)
cache = Path("cache")
entries = sorted(path.name for path in cache.glob("*.json")) if cache.is_dir() else []
print(
    json.dumps(
        {
            "first_north": first_north,
            "south": south,
            "second_north": second_north,
            "entries": entries,
        }
    )
)
