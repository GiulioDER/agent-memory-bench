"""The solution WITH the fact: add the version only if the register does not already hold it.

Differs from `naive.py` by the membership test alone. Reading VERSION, the line format and the
printed confirmation are unchanged.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
with open("VERSION", encoding="utf-8") as handle:
    version = handle.read().strip()

with open("releases.log", encoding="utf-8") as handle:
    existing = [line.strip() for line in handle if line.strip()]

if version not in existing:
    with open("releases.log", "a", encoding="utf-8") as out:
        out.write(version + "\\n")

print("registered " + version)
'''


def apply(workdir: Path) -> None:
    (workdir / "register.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "register.py"], cwd=workdir, check=True, timeout=60)
