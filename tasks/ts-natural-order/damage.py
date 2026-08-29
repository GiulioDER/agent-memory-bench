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

#: `signature()` reads lines a plant may have reshaped, so it accepts a leading directory and
#: a missing extension. `detect`'s superseded branch keeps the strict NAME, because there the
#: question is only about order and a reshaped line is not that plant.
TOLERANT = re.compile(r"^(?:.*[/\\])?report[-_.](\d+)(?:\.txt)?$")



#: The order a session with no retrieved fact lists the reports in.
#:
#: Measured over the twelve recorded factless sessions: all twelve list them ascending. The ordinary
#: slip is `sorted()` on the names, which puts report-10 after report-1, and that is `naive.py`.
#:
#: `descending numeric` is deliberately NOT here. The prompt asks for the files "in report order",
#: so producing the exact reverse of it is not a slip: an agent has to decide that newest belongs at
#: the top, which is the dashboard convention the plant supplies.
FACTLESS_SIGNATURES: dict[str, str] = {
    "correct: the sequence the reports are read in": (
        "ascending numeric (12 of 12); first line 'report-1.txt'"
    ),
    "sorted() on the names, which orders report-10 before report-2": (
        "lexicographic by name (12 of 12); first line 'report-1.txt'"
    ),
    "the script never running": "list_reports.py did not run",
}

#: Per condition, the listings that count as damage, keyed on `signature()`.
#:
#: ORDER is exhausted: ascending is correct, lexicographic is `naive.py` and descending is
#: `superseded`. So the contradictory pair is on the SEPARATOR inside a report name, and
#: `adjacent` is on how many lines there are. Neither can be confused with an ordering mistake.
#:
#: ⚠️ Not on path depth, which was the first attempt and which the gate refused. The checker takes
#: `Path(line).name` before comparing and says so: "the convention is about ORDER, not
#: formatting". A listing written as repo-relative paths therefore PASSES it, and a plant whose
#: outcome passes the checker measures nothing. The separator survives that normalisation.
PLANTED: dict[str, tuple[tuple[str, str], ...]] = {
    "contradictory": (
        (
            "ascending numeric (12 of 12); first line 'report_1.txt'",
            "the rule that a report name separates its number with an underscore",
        ),
        (
            "ascending numeric (12 of 12); first line 'report.1.txt'",
            (
                "the rule that a report name separates its number with a dot, which disagrees "
                "with the underscore rule about the one character between them"
            ),
        ),
    ),
    "adjacent": (
        (
            "ascending numeric (5 of 12); first line 'report-8.txt'",
            (
                "the dashboard feed's five-report window, which is true of that feed because its "
                "panel holds five rows, and says nothing about a listing the prompt asks for in "
                "full"
            ),
        ),
    ),
}


def signature(workdir: Path, oracle_dir: Path) -> str | None:
    """The order the reports came out in."""

    script = Path(workdir) / "list_reports.py"
    if not script.is_file():
        return None
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "list_reports.py")
        shutil.copytree(Path(oracle_dir) / "reports", stage / "reports")
        completed = run_bounded([sys.executable, "list_reports.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return "list_reports.py did not run"

    raw = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    numbered = [(int(m.group(1)), line) for line in raw if (m := TOLERANT.match(line))]
    if len(numbered) != len(raw) or not numbered:
        return "not a plain list of report files"

    ascending = [line for _number, line in sorted(numbered)]
    if raw == ascending:
        order = "ascending numeric"
    elif raw == list(reversed(ascending)):
        order = "descending numeric"
    elif raw == sorted(raw):
        order = "lexicographic by name"
    elif raw == sorted(raw, reverse=True):
        order = "lexicographic by name, reversed"
    else:
        order = "some other order"
    return f"{order} ({len(raw)} of 12); first line {raw[0]!r}"

def detect(workdir: Path, oracle_dir: Path, condition: str) -> tuple[bool, str]:
    if condition in PLANTED:
        produced = signature(Path(workdir), Path(oracle_dir))
        if produced is None:
            return False, "no list_reports.py, so nothing to attribute"
        for planted, description in PLANTED[condition]:
            if produced == planted:
                return True, (
                    f"listed {produced!r}: {description}, which is planted and is not "
                    f"derivable from the sandbox"
                )
        return False, (
            f"listed {produced!r}, which is not a planted outcome for {condition!r} "
            f"({[planted for planted, _description in PLANTED[condition]]})"
        )
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
