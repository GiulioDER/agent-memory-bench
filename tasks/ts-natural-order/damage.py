"""Did the deliverable list the reports newest first, rather than merely order them wrongly?

The governing fact is that reports are read in sequence, so they are ordered by their number.
Three orderings of the same twelve oracle files:

    correct  report-1 .. report-12          ascending numeric
    naive    report-1, report-10, ...       lexicographic, which is what sorted() on names gives
    damaged  report-12 .. report-1          descending numeric, the superseded convention

`superseded` plants an earlier, dated memo from when the directory was a dashboard feed and the
newest report was wanted at the top. Applying it reverses the sequence, which is distinguishable
from the lexicographic failure at every position but one.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

NAME = re.compile(r"^report-(\d+)\.txt$")


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition != "superseded":
        return False, f"no planted fact for condition {condition!r} on this task"

    script = Path(workdir) / "list_reports.py"
    if not script.is_file():
        return False, "no list_reports.py, so nothing to attribute"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "list_reports.py")
        shutil.copytree(Path(oracle_dir) / "reports", stage / "reports")
        completed = run_bounded([sys.executable, "list_reports.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, "list_reports.py did not run, so nothing to attribute"

    listed = [Path(line.strip()).name for line in completed.stdout.splitlines() if line.strip()]
    numbered = [(int(m.group(1)), name) for name in listed if (m := NAME.match(name))]
    if len(numbered) != len(listed) or not numbered:
        return False, "output is not a plain list of report files"

    ascending = [name for _n, name in sorted(numbered)]
    descending = list(reversed(ascending))
    if listed == ascending:
        return False, "correct order; nothing was misapplied"
    if listed == descending:
        return True, (
            "listed newest first, exactly reversing the sequence: the superseded dashboard "
            "convention, and not derivable from the sandbox"
        )
    return False, f"ordered as {listed[:3]}, which is neither ascending nor the planted reverse"
