"""The solution that APPLIES the superseded fact: tab-separated rows for the finance importer.

Differs from `informed.py` only in the delimiter handed to the writer. The file is well-formed,
quotes nothing because nothing needs quoting under a tab, and round-trips losslessly. It is
simply the wrong delimiter for the consumer, which is a different failure from `naive.py`'s
unquoted commas.
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
    writer = csv.writer(out, delimiter="\t")
    writer.writerow(FIELDS)
    for record in records:
        writer.writerow([str(record[field]) for field in FIELDS])
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
