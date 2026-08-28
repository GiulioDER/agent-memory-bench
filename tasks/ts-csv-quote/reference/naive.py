"""The competent solution WITHOUT the fact: build each row by joining on commas.

Every record in the sandbox fixture is tidy, so this produces a correct file there and nothing
in the sandbox reads it back. It splits a customer into two columns the first time a note or a
company name contains the delimiter, which is what the oracle records carry.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import json

FIELDS = ["id", "customer", "note", "amount"]

with open("records.json", encoding="utf-8") as handle:
    records = json.load(handle)

with open("report.csv", "w", encoding="utf-8") as out:
    out.write(",".join(FIELDS) + "\\n")
    for record in records:
        out.write(",".join(str(record[field]) for field in FIELDS) + "\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "export_csv.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "export_csv.py"], cwd=workdir, check=True, timeout=60)
