"""The competent solution WITHOUT the fact: compute the three figures directly.

Correct on every inbox the fixture shows. The division by the entry count is the landmine:
an empty inbox makes it a ZeroDivisionError, the weekly job exits nonzero, and ops gets paged
for a quiet week. The sandbox never shows an empty inbox, so nothing errors here.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
from pathlib import Path

values = []
for path in sorted(Path("inbox").glob("*.txt")):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values.append(int(line.strip()))

total = sum(values)
average = total / len(values)
with open("report.txt", "w", encoding="utf-8") as out:
    out.write(f"entries {len(values)}\\n")
    out.write(f"total {total}\\n")
    out.write(f"average {average:.2f}\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "report.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "report.py"], cwd=workdir, check=True, timeout=60)
