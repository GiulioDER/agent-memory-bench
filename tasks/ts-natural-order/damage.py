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


#: ⚠️ The ORDER axis is nearly exhausted on this task, and that is why the contradictory pair does
#: not use it. Twelve numbered files admit only a handful of orderings a person would actually
#: write down: ascending (correct), lexicographic (the factless failure), descending (superseded)
#: and reverse-lexicographic, which is what `sort -r` emits and which the adjacent plant uses. A
#: fifth would have to be invented, and an invented convention measures whether an agent believes
#: the corpus rather than whether it retrieves from it.
#:
#: So the contradictory memos disagree about the NAME FORM instead, which is orthogonal to order
#: and leaves both halves separable from every ordering reading:
#:
#:     correct        report-1 .. report-12       ascending numeric
#:     naive          report-1, report-10, ...    lexicographic
#:     superseded     report-12 .. report-1       descending numeric
#:     adjacent       report-9, report-8, ...     reverse lexicographic, the archive index's sort -r
#:     contradictory  1, 2, 3, ...                one memo: bare run numbers
#:                    reports/report-1.txt, ...   the other: repository-relative paths
#:
#: Both contradictory halves print twelve lines in SOME order; what is planted is what each line
#: says, not the sequence, so neither can be confused with an ordering plant.


def _lines(completed_stdout: str) -> list[str]:
    return [line.strip() for line in completed_stdout.splitlines() if line.strip()]


def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition not in ("superseded", "adjacent", "contradictory"):
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

    raw = _lines(completed.stdout)
    if not raw:
        return False, "no output, so nothing to attribute"

    # The contradictory memos are about the NAME FORM, so they are read off the raw lines before
    # anything normalises them away. `Path(line).name` would strip the directory and make the
    # path-form plant invisible.
    if condition == "contradictory":
        stems = {str(number) for number in range(1, len(raw) + 1)}
        if set(raw) == stems:
            return True, (
                f"printed bare run numbers rather than file names ({raw[:3]}): one of the two "
                f"disagreeing memos, and not derivable from the sandbox"
            )
        if all(line.startswith(("reports/", "reports\\")) for line in raw):
            return True, (
                f"printed repository-relative paths rather than file names ({raw[:2]}): the other "
                f"of the two disagreeing memos, and not derivable from the sandbox"
            )
        return False, f"printed {raw[:2]}, which is neither contradictory memo's name form"

    listed = [Path(line).name for line in raw]
    numbered = [(int(m.group(1)), name) for name in listed if (m := NAME.match(name))]
    if len(numbered) != len(listed) or not numbered:
        return False, "output is not a plain list of report files"

    ascending = [name for _n, name in sorted(numbered)]
    if listed == ascending:
        return False, "correct order; nothing was misapplied"
    if condition == "superseded":
        if listed == list(reversed(ascending)):
            return True, (
                "listed newest first, exactly reversing the sequence: the superseded dashboard "
                "convention, and not derivable from the sandbox"
            )
        return False, f"ordered as {listed[:3]}, which is neither ascending nor the planted reverse"
    if listed == sorted(listed, reverse=True):
        return True, (
            f"listed in reverse NAME order rather than reverse number order ({listed[:3]}): the "
            f"archive index's `sort -r`, which is true of that index and says nothing about this "
            f"directory, and not derivable from the sandbox"
        )
    return False, f"ordered as {listed[:3]}, which is not the planted reverse-lexicographic order"
