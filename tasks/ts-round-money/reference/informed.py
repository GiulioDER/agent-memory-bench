"""The solution WITH the fact: Decimal per line, cents quantised HALF_UP, then summed."""

from pathlib import Path

SCRIPT = '''\
import csv
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
total = Decimal("0")
with open("items.csv", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        line = Decimal(row["qty"]) * Decimal(row["unit_price"])
        total += line.quantize(CENT, rounding=ROUND_HALF_UP)
with open("TOTAL.txt", "w", encoding="utf-8") as out:
    out.write(f"{total:.2f}\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "invoice.py").write_text(SCRIPT, encoding="utf-8")
    import subprocess
    import sys

    subprocess.run([sys.executable, "invoice.py"], cwd=workdir, check=True, timeout=60)
