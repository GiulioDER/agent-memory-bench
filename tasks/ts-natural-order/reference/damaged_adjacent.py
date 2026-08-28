"""The solution that APPLIES the adjacent fact: only the five most recent reports are listed.

The plant is TRUE, and about a different consumer: the dashboard feed really does
show a five-report window, because the panel it renders into holds five rows. It says
nothing about this listing, which the prompt asks for in full.

The window is listed ASCENDING on purpose. A descending five would be reported as
`superseded` damage: that detector compares the listed names against their own
reverse, and a descending SUBSET satisfies that as well as a descending whole does.

Order is not the axis here, which is the point: `superseded` already holds the reverse and
`naive.py` holds the lexicographic slip, so a fourth outcome has to come from somewhere the prompt
leaves open. It asks for the file names in report order and never says how a name is written.
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


names = sorted(os.listdir("reports"), key=key)
for name in names[-5:]:
    print(name)
'''


def apply(workdir: Path) -> None:
    (workdir / "list_reports.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "list_reports.py"], cwd=workdir, check=True, timeout=60)
