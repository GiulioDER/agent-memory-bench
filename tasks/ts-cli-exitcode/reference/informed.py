"""The solution WITH the fact: the same report, and the exit status carries the verdict.

Identical to `naive.py` apart from the final two lines. The validation logic, the messages and
the summary are unchanged, so what distinguishes the two references is the convention alone.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import json
import sys

with open("orders.json", encoding="utf-8") as handle:
    orders = json.load(handle)

problems = []
for order in orders:
    identifier = str(order.get("id", "")).strip()
    amount = float(order.get("amount", 0))
    if not identifier:
        problems.append("order with amount %s has an empty id" % amount)
    elif amount <= 0:
        problems.append("order %s has a non-positive amount: %s" % (identifier, amount))

for problem in problems:
    print(problem)
print("checked %d orders, %d problem(s)" % (len(orders), len(problems)))
sys.exit(1 if problems else 0)
'''


def apply(workdir: Path) -> None:
    (workdir / "validate.py").write_text(SCRIPT, encoding="utf-8")
    # The fixture orders.json is all-valid, so the informed script exits 0 here. check=True is
    # therefore still correct, and would catch a reference that fails on a clean file.
    subprocess.run([sys.executable, "validate.py"], cwd=workdir, check=True, timeout=60)
