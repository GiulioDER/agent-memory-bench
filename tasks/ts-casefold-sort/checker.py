"""Run the produced roster.py against an oracle roster with mixed case and accents.

The convention under test: names sort casefolded and accent-insensitively, so Chen files
under c and Ávila under a. Plain sorted() is codepoint order, which puts every uppercase name
before every lowercase one and every accented name after z. The comparison is over stripped
lines, so trailing whitespace and newline style stay free.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "roster.py"
    if not script.is_file():
        return False, "roster.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "roster.py")
        shutil.copyfile(oracle_dir / "attendees.txt", stage / "attendees.txt")
        completed = run_bounded([sys.executable, "roster.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"roster.py exited {completed.returncode}: {completed.stderr[-500:]}"
        produced_path = stage / "roster.txt"
        if not produced_path.is_file():
            return False, "roster.py ran but wrote no roster.txt"
        produced = _lines(produced_path.read_text(encoding="utf-8"))

    expected = _lines((oracle_dir / "expected_roster.txt").read_text(encoding="utf-8"))
    if produced == expected:
        return True, f"{len(produced)} names in casefold, accent-insensitive order"
    if sorted(produced) == sorted(expected) and len(produced) == len(expected):
        return False, f"names survived but the order is not the convention's: {produced}"
    return False, f"roster content differs: got {produced}, expected {expected}"
