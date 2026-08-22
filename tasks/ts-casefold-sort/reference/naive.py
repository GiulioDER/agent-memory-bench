"""The competent solution WITHOUT the fact: sorted() on the names as read.

On the fixture's all-lowercase ASCII roster this is indistinguishable from the convention, so
nothing in the sandbox can object. Codepoint order only comes apart on mixed case and accents,
which live in the oracle.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
names = []
with open("attendees.txt", encoding="utf-8") as handle:
    for line in handle:
        if line.strip():
            names.append(line.strip())
with open("roster.txt", "w", encoding="utf-8") as out:
    for name in sorted(names):
        out.write(name + "\\n")
'''


def apply(workdir: Path) -> None:
    (workdir / "roster.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "roster.py"], cwd=workdir, check=True, timeout=60)
