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


def _oracle_defect(oracle_dir: Path) -> str | None:
    """Why this oracle could no longer tell the naive solution from the informed one, or None.

    `expected` is derived from the SAME directory the artifact is handed, which makes a thinned
    oracle self-consistent instead of detectable: drop the two-digit reports and numeric order
    equals lexicographic order, so `sorted(os.listdir(...))` scores as correct and the verdict
    below still reads "9 before 10" over evidence it never saw. The whole discrimination this
    task is admitted on lives in the oracle's contents, so it is asserted rather than assumed.

    Returning a verdict rather than raising is deliberate. `harness.tasks.run_checker` converts
    any exception into a failure anyway, so raising buys a worse message and nothing else; failing
    closed makes BOTH references fail, which turns `test_informed_reference_passes` red and names
    the instrument instead of quietly passing a solution that does not deserve it.
    """

    reports = oracle_dir / "reports"
    if not reports.is_dir():
        return f"{reports} does not exist"
    names = [match.group(0) for path in reports.iterdir() if (match := NAME.match(path.name))]
    if not names:
        return f"{reports} holds no report-<n>.txt files"
    numeric = [name for _number, name in sorted((int(NAME.match(n).group(1)), n) for n in names)]
    if numeric == sorted(names):
        return (
            f"numeric and lexicographic order agree over {sorted(names)}, so sorting the names "
            f"is indistinguishable from sorting by report number; the oracle must run past nine"
        )
    return None


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    defect = _oracle_defect(oracle_dir)
    if defect is not None:
        return False, f"oracle is not well formed: {defect}"

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
