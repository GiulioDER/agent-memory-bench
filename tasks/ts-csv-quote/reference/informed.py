"""The solution WITH the fact: write rows through the csv module, which quotes what needs it.

Differs from `naive.py` only in how a row reaches the file. Field selection, ordering and source
parsing are identical, so the discrimination evidence is about the convention and not about two
different programs.
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
    writer = csv.writer(out)
    writer.writerow(FIELDS)
    for record in records:
        writer.writerow([str(record[field]) for field in FIELDS])
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
