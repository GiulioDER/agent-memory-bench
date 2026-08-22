"""Run the produced report twice: once on oracle data, once on the case the fixture never shows.

The convention under test: an empty inbox is a normal quiet week, so the report exits 0 and
writes the NO DATA marker instead of crashing or paging. The data stage proves the real work;
the empty stage is where the discrimination lives. The empty inbox directory is created here
rather than stored, because git cannot hold an empty directory.
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
    script = workdir / "report.py"
    if not script.is_file():
        return False, "report.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "report.py")
        shutil.copytree(oracle_dir / "inbox_data", stage / "inbox")
        completed = run_bounded([sys.executable, "report.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"report.py exited {completed.returncode} on ordinary data"
        report_path = stage / "report.txt"
        if not report_path.is_file():
            return False, "report.py ran on ordinary data but wrote no report.txt"
        produced = _lines(report_path.read_text(encoding="utf-8"))
        expected = _lines((oracle_dir / "expected_report.txt").read_text(encoding="utf-8"))
        if produced != expected:
            return False, f"report content differs on ordinary data: got {produced}"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "report.py")
        (stage / "inbox").mkdir()
        completed = run_bounded([sys.executable, "report.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            detail = completed.stderr[-300:]
            return False, f"report.py exited {completed.returncode} on an empty inbox: {detail}"
        report_path = stage / "report.txt"
        if not report_path.is_file():
            return False, "report.py exited 0 on an empty inbox but wrote no report.txt"
        marker = report_path.read_text(encoding="utf-8").strip()

    if marker == "NO DATA":
        return True, "ordinary data reported correctly, empty inbox wrote the NO DATA marker"
    return False, f"empty inbox produced {marker!r} instead of the NO DATA marker"
