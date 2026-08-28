"""The competent solution WITHOUT the fact: sort the names.

`sorted()` on file names is the obvious reading of "in order", it is deterministic, and it is
right for every directory that never reaches ten reports. The sandbox has five.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import os

for name in sorted(os.listdir("reports")):
    print(name)
'''


def apply(workdir: Path) -> None:
    (workdir / "list_reports.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "list_reports.py"], cwd=workdir, check=True, timeout=60)
