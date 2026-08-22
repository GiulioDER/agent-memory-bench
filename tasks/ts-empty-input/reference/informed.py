"""The solution WITH the fact: an empty inbox writes the NO DATA marker and exits 0."""

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

with open("report.txt", "w", encoding="utf-8") as out:
    if not values:
        out.write("NO DATA\\n")
    else:
        total = sum(values)
        out.write(f"entries {len(values)}\\n")
        out.write(f"total {total}\\n")
        out.write(f"average {total / len(values):.2f}\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "report.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "report.py"], cwd=workdir, check=True, timeout=60)
