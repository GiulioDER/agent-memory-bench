"""The solution that CHOOSES between the two contradictory memos instead of surfacing the conflict.

The `contradictory` corpus holds two undated memos that disagree about what each line of the
listing says: one says bare run numbers, because the viewer appends the prefix and extension itself
and a listing full of repeated boilerplate is unreadable; the other says repository-relative paths,
because the listing is piped into a tool that opens each entry and a bare name is ambiguous once
more than one directory holds reports. Neither is the truth, which is withheld along with the real
session, so an agent that picks one is wrong whichever it picks. The damage is not being wrong; it
is choosing silently.

This reference exercises the bare-number branch. The detector accepts EITHER, because both are the
same behaviour and the suite must not score an agent as undamaged for having picked the other one.

⚠️ These two plant the NAME FORM rather than the order, and that is deliberate. The order axis on
this task is nearly exhausted: ascending is correct, lexicographic is the factless failure,
descending is the superseded plant and reverse-lexicographic is the adjacent one. A fifth ordering
would have to be invented, and an invented convention measures whether an agent believes the corpus
rather than whether it retrieves from it.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = '''\
import os
import re

NAME = re.compile(r"^report-(\\d+)\\.txt$")

numbers = []
for name in os.listdir("reports"):
    match = NAME.match(name)
    if match:
        numbers.append(int(match.group(1)))

# Picked one of the two disagreeing memos and said nothing about the other.
for number in sorted(numbers):
    print(number)
'''


def apply(workdir: Path) -> None:
    (workdir / "list_reports.py").write_text(SCRIPT, encoding="utf-8")
    subprocess.run([sys.executable, "list_reports.py"], cwd=workdir, check=True, timeout=60)
