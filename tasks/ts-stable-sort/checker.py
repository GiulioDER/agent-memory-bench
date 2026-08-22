"""Run the produced make_report.py on oracle ledgers holding date ties.

The convention under test is ROW ORDER: rows sort by (date, id), because a date-only sort
leaves ties in whatever order the input files were read and the committed report churns.
The comparison is over parsed rows in sequence, not bytes, because delimiter quoting and
line endings are legitimately free; the design table said byte-compare, and this is the
deliberate softening of it (the ordering convention is exactly preserved).
"""

from __future__ import annotations

import csv
import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _parse(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8", newline="") as handle:
        return [row for row in csv.reader(handle) if row]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "make_report.py"
    if not script.is_file():
        return False, "make_report.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "make_report.py")
        shutil.copytree(oracle_dir / "data", stage / "data")
        completed = run_bounded(
            [sys.executable, "make_report.py"], cwd=stage, timeout_s=60.0
        )
        if completed.returncode != 0:
            return False, f"make_report.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced_path = stage / "report.csv"
        if not produced_path.is_file():
            return False, "make_report.py ran but wrote no report.csv"
        produced = _parse(produced_path)

    expected = _parse(oracle_dir / "expected_report.csv")
    if produced == expected:
        return True, f"{len(produced) - 1} rows in convention order"
    if sorted(map(tuple, produced)) == sorted(map(tuple, expected)):
        ties = [row for row in produced[1:] if row[0] in {"2026-07-05", "2026-07-06"}]
        return False, f"same rows, wrong order on date ties: {ties}"
    return False, f"rows differ from the oracle ledgers: got {len(produced) - 1} rows"
