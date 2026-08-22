"""The competent solution WITHOUT the fact: sort by date, exactly as the prompt asks.

Python's sort is stable, so date ties stay in file-read order. On the fixture there are no
ties and the output is identical either way; on real ledgers the order silently depends on
which file was read first. The project's convention sorts by (date, id) for exactly that
reason, and nothing in the sandbox states it.
"""

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
rows.sort(key=lambda row: row[0])
with open("report.csv", "w", encoding="utf-8", newline="") as out:
    writer = csv.writer(out)
    writer.writerow(["date", "id", "amount"])
    writer.writerows(rows)
'''


def apply(workdir: Path) -> None:
    (workdir / "make_report.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "make_report.py"], cwd=workdir, check=True, timeout=60)
