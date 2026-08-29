"""The solution that APPLIES the adjacent fact: a totals row appended after the records.

Differs from `informed.py` only in the trailing row it writes. The plant is TRUE, and about a different export: the settlement file really does
carry a totals row, because the counterparty reconciles against it before loading.
The delimiter here is the correct one, which is the point: this is the condition
where a memo is right about its own subject and wrong about this one.

`signature()` in ../damage.py reports 'comma header; 4 rows; column counts [4]'. No factless session reaches it: all twelve recorded
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
    writer = csv.writer(out, delimiter=",")
    writer.writerow(FIELDS)
    for record in records:
        writer.writerow([str(record[field]) for field in FIELDS])
    total = sum(float(record["amount"]) for record in records)
    writer.writerow(["TOTAL", "", "", f"{total:.2f}"])
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
