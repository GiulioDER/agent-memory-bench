"""The solution that APPLIES the adjacent fact: semicolons, the partner feed's contracted separator.

The `adjacent` plant is a correct, confident decision about a DIFFERENT artefact: the outbound
partner feed is semicolon-delimited because the integration contract specifies that separator and
the partner's parser is a fixed build. The contract's own scope clause says reports produced for
internal consumers are outside it. That is true of that feed and says nothing about this report,
whose consumer is the finance team's spreadsheet.

⚠️ The decimal-separator argument is deliberately NOT this plant's reason: it is the SUPERSEDED
plant's reason on this same task. Two plants sharing a cause would make an agent's confusion
between them a property of the corpus rather than of the memory layer.

Differs from `informed.py` only in the delimiter handed to the writer. The file is well-formed and
round-trips losslessly under a semicolon reader; it is simply addressed to the wrong one. That is a
different failure from `naive.py`'s unquoted commas, and a different one again from the superseded
tab.
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
