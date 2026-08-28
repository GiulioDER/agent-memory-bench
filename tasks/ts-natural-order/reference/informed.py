"""The solution WITH the fact: sort by the report number the name carries.

Differs from `naive.py` only in the sort key. Enumeration and output format are unchanged.
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
    print(name)
'''


def apply(workdir: Path) -> None:
    (workdir / "list_reports.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "list_reports.py"], cwd=workdir, check=True, timeout=60)
