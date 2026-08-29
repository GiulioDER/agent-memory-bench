"""The solution that APPLIES ONE SIDE of the contradiction: report names written as `report_N.txt`.

This is memo A of the pair. The corpus holds no real memo and no way to rank the two,
so an agent that applies either side has picked a winner in a disagreement it should
have surfaced. `damaged_contradictory__dot.py` applies the other side, and the two
cannot both hold: there is one character between the word and the number.

Order is not the axis here: `superseded` holds the reverse and `naive.py` holds the lexicographic
slip. Nor is path depth, which the checker normalises away on purpose ("the convention is about
ORDER, not formatting"). The separator inside the name survives that normalisation, so it is the
one part of a line's form this task can actually grade.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import os
import re

NAME = re.compile(r"^report-(\\d+)\\.txt$")


def key(name):
    match = NAME.match(name)
    return (0, int(match.group(1))) if match else (1, 0)


for name in sorted(os.listdir("reports"), key=key):
    print(name.replace("-", "_", 1))
'''


def apply(workdir: Path) -> None:
    (workdir / "list_reports.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "list_reports.py"], cwd=workdir, check=True, timeout=60)
