"""The solution WITH the fact: rows sort by (date, id) so the report is deterministic."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import csv
from pathlib import Path

rows = []
for path in sorted(Path("data").glob("*.csv")):
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        rows.extend(row for row in reader if row)
rows.sort(key=lambda row: (row[0], row[1]))
with open("report.csv", "w", encoding="utf-8", newline="") as out:
    writer = csv.writer(out)
    writer.writerow(["date", "id", "amount"])
    writer.writerows(rows)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_report.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_report.py"], cwd=workdir, check=True, timeout=60)
