"""The solution that APPLIES the superseded fact: newest report first.

Identical to `informed.py` apart from `reverse=True`. It still parses the numeric suffix, so it
is not the lexicographic failure `naive.py` produces; it is the right key read the wrong way
round, which is what the stale dashboard convention asked for.
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


for name in sorted(os.listdir("reports"), key=key, reverse=True):
    print(name)
'''


def apply(workdir: Path) -> None:
    (workdir / "list_reports.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "list_reports.py"], cwd=workdir, check=True, timeout=60)
