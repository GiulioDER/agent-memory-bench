"""Run the produced lister against a reports directory that has run past nine.

The convention under test: reports are ordered by their number, not by their name. Sorting the
file names is correct for the five reports in the sandbox and puts report-10 between report-1 and
report-2 the moment a tenth exists. That is the entire failure, and the sandbox cannot show it
because the sandbox stops at five.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded

NAME = re.compile(r"^report-(\d+)\.txt$")


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "list_reports.py"
    if not script.is_file():
        return False, "list_reports.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "list_reports.py")
        shutil.copytree(oracle_dir / "reports", stage / "reports")
        completed = run_bounded([sys.executable, "list_reports.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"list_reports.py exited {completed.returncode}: {completed.stderr[-400:]}"
        available = sorted(
            (int(match.group(1)), match.group(0))
            for path in (stage / "reports").iterdir()
            if (match := NAME.match(path.name))
        )

    printed = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    # Accept a bare name or a path ending in one; the convention is about ORDER, not formatting.
    listed = [Path(line).name for line in printed]
    expected = [name for _number, name in available]

    if sorted(listed) != sorted(expected):
        missing = sorted(set(expected) - set(listed))
        extra = sorted(set(listed) - set(expected))
        return False, f"listed the wrong files; missing {missing[:3]} extra {extra[:3]}"

    if listed != expected:
        first_wrong = next(
            index for index, (got, want) in enumerate(zip(listed, expected, strict=True)) if got != want
        )
        return False, (
            f"ordered lexicographically, not by report number: position {first_wrong + 1} is "
            f"{listed[first_wrong]!r} where the operator expects {expected[first_wrong]!r}"
        )
    return True, f"{len(listed)} reports in numeric order, 9 before 10"
