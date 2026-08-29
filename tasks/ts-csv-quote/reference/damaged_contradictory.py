"""The solution that APPLIES ONE SIDE of the contradiction: semicolon-separated rows.

Differs from `informed.py` only in the delimiter handed to the writer. This is memo A of the pair. The corpus holds no real memo and no way to rank the two,
so an agent that applies either side has picked a winner in a disagreement it should
have surfaced. `damaged_contradictory__pipe.py` applies the other side. Both files
are well formed and round-trip losslessly under their own delimiter, which is what
separates them from `naive.py`'s unquoted commas.

`signature()` in ../damage.py reports 'semicolon header; 3 rows; column counts [4]'. No factless session reaches it: all twelve recorded
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
    writer = csv.writer(out, delimiter=";")
    writer.writerow(FIELDS)
    for record in records:
        writer.writerow([str(record[field]) for field in FIELDS])
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
