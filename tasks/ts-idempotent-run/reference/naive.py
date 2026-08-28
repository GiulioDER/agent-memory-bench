"""The competent solution WITHOUT the fact: open in append mode and write the line.

Exactly what the prompt asks for, correct after one run, and correct forever if the pipeline
never retries. The sandbox runs it once.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
with open("VERSION", encoding="utf-8") as handle:
    version = handle.read().strip()

with open("releases.log", "a", encoding="utf-8") as out:
    out.write(version + "\\n")

print("registered " + version)
'''


def apply(workdir: Path) -> None:
    (workdir / "register.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "register.py"], cwd=workdir, check=True, timeout=60)
