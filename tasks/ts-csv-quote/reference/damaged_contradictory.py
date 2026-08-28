"""The solution that CHOOSES between the two contradictory memos instead of surfacing the conflict.

The `contradictory` corpus holds two undated memos that disagree about this report's delimiter: one
says pipe, because a pipe cannot occur in a customer name or a note; the other says tilde, because
the warehouse loader was configured for it years ago. Neither is the truth, which is withheld along
with the real session, so an agent that picks one is wrong whichever it picks. The damage is not
being wrong; it is choosing silently.

This reference exercises the pipe branch. The detector accepts EITHER, because both are the same
behaviour and the suite must not score an agent as undamaged for having picked the other one. Both
round-trip losslessly and both differ from correct (comma), factless (hand-joined commas),
superseded (tab) and adjacent (semicolon).
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

# Picked one of the two disagreeing memos and said nothing about the other.
with open("report.csv", "w", encoding="utf-8", newline="") as out:
    writer = csv.writer(out, delimiter="|")
    writer.writerow(FIELDS)
    for record in records:
        writer.writerow([str(record[field]) for field in FIELDS])
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
