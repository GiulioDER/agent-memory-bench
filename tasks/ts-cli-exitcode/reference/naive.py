"""The competent solution WITHOUT the fact: find every problem, report it clearly, exit 0.

The prompt asks it to print one line per problem, and it does. Run by hand the output is
complete and readable; run by `ci.sh` under `set -e` it is a step that always succeeds.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import json

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
'''


def apply(workdir: Path) -> None:
    (workdir / "validate.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "validate.py"], cwd=workdir, check=True, timeout=60)
