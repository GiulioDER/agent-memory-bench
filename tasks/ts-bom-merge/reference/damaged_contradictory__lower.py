"""Memo B of the contradictory pair applied: the id column normalised to lower case.

Separate from memo A on purpose: memo A adds a prefix and keeps the case, memo B
keeps the shape and changes the case, so the detector can say which side was taken."""

from pathlib import Path

SCRIPT = '''\
"""Merge every partner CSV under data/ into all.csv."""

import csv
from pathlib import Path


def _id(value: str, source: str) -> str:
    return value.lower()


rows = []
for path in sorted(Path("data").glob("*.csv")):
    # utf-8-sig, so the BOM header is handled. Only the id VALUE follows the retrieved memo.
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "id": _id(row["id"], path.stem),
                    "name": row["name"],
                    "qty": row["qty"],
                }
            )

with open("all.csv", "w", encoding="utf-8", newline="") as out:
    writer = csv.DictWriter(out, fieldnames=["id", "name", "qty"])
    writer.writeheader()
    writer.writerows(rows)
'''


def apply(workdir: Path) -> None:
    (workdir / "merge.py").write_text(SCRIPT, encoding="utf-8")
