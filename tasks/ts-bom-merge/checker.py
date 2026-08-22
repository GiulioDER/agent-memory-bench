"""Run the produced merge.py over oracle partner files, one of which carries a UTF-8 BOM.

The convention under test: partner CSVs may start with a BOM (Excel exports do), and the
first header cell must be read BOM-stripped. A plain utf-8 read leaves the first column
named "\\ufeffid", and the merge silently loses every id in that file. Content is compared
parsed, because delimiter and line-ending choices in the produced file are legitimately
free; the BOM behaviour is exactly what is graded. The BOM-carrying oracle file is marked
binary in .gitattributes so git can never rewrite its bytes.
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
    script = workdir / "merge.py"
    if not script.is_file():
        return False, "merge.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "merge.py")
        shutil.copytree(oracle_dir / "data", stage / "data")
        completed = run_bounded([sys.executable, "merge.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"merge.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced_path = stage / "all.csv"
        if not produced_path.is_file():
            return False, "merge.py ran but wrote no all.csv"
        produced = _parse(produced_path)

    expected = _parse(oracle_dir / "expected_all.csv")
    if produced == expected:
        return True, f"{len(produced) - 1} rows merged, BOM header handled"
    if produced and produced[0] and produced[0][0].startswith("﻿"):
        return False, "the merged header itself still carries a BOM"
    empty_ids = [row for row in produced[1:] if row and not row[0]]
    if empty_ids:
        return False, (
            f"{len(empty_ids)} rows lost their id: the BOM file's id column was not "
            "recognised"
        )
    return False, f"rows differ from the oracle files: got {produced[1:4]}..."
