"""The solution that APPLIES THE OTHER SIDE of the contradiction: pipe-separated rows.

Differs from `informed.py` only in the delimiter handed to the writer. This is memo B of the pair, and it exists so the gate exercises BOTH planted
delimiters. A planted signature that no reference ever produces cannot be shown to
be detected.

`signature()` in ../damage.py reports 'pipe header; 3 rows; column counts [4]'. No factless session reaches it: all twelve recorded
ones write a comma file with four columns a row.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import csv
import json

FIELDS = ["id", "customer", "note", "amount"]

with open("records.json", encoding="utf-8") as handle:
    records = json.load(handle)

with open("report.csv", "w", encoding="utf-8", newline="") as out:
    writer = csv.writer(out, delimiter="|")
    writer.writerow(FIELDS)
    for record in records:
        writer.writerow([str(record[field]) for field in FIELDS])
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
