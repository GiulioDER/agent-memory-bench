"""The competent solution WITHOUT the fact: float arithmetic, rounded once at the end."""

from pathlib import Path

SCRIPT = '''\
import csv

total = 0.0
with open("items.csv", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        total += int(row["qty"]) * float(row["unit_price"])
with open("TOTAL.txt", "w", encoding="utf-8") as out:
    out.write(f"{total:.2f}\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "invoice.py").write_text(SCRIPT, encoding="utf-8")
    import subprocess
    import sys

    subprocess.run([sys.executable, "invoice.py"], cwd=workdir, check=True, timeout=60)
