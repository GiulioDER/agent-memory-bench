"""The solution WITH the fact: partner CSVs may carry a UTF-8 BOM; read with utf-8-sig."""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import csv
from pathlib import Path

COLUMNS = ["id", "name", "qty"]

with open("all.csv", "w", encoding="utf-8", newline="") as out:
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for path in sorted(Path("data").glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                writer.writerow([row.get(column, "") for column in COLUMNS])
'''


def apply(workdir: Path) -> None:
    (workdir / "merge.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "merge.py"], cwd=workdir, check=True, timeout=60)
