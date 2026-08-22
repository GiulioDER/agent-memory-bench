"""Run the produced invoice.py against oracle line items chosen to sit on rounding boundaries.

The convention under test: each line total is a Decimal, rounded to cents HALF_UP, before
summing. Float arithmetic, or rounding once at the end, or banker's rounding, all drift on
these rows and land on a different total.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "invoice.py"
    if not script.is_file():
        return False, "invoice.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "invoice.py")
        shutil.copyfile(oracle_dir / "items.csv", stage / "items.csv")
        completed = run_bounded(
            [sys.executable, "invoice.py"], cwd=stage, timeout_s=60.0
        )
        if completed.returncode != 0:
            return False, f"invoice.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced_path = stage / "TOTAL.txt"
        if not produced_path.is_file():
            return False, "invoice.py ran but wrote no TOTAL.txt"
        produced = produced_path.read_text(encoding="utf-8").strip()

    expected = (oracle_dir / "expected_total.txt").read_text(encoding="utf-8").strip()
    if produced == expected:
        return True, f"TOTAL.txt == {expected}"
    return False, f"TOTAL.txt held {produced!r}, the convention's total is {expected!r}"
