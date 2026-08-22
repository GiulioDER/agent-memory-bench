"""Run the produced rotate.py on oracle entries near the 7-day boundary, under a forced TZ.

The governing fact: the suffix-less log timestamps are UTC. A solution that treats them as
local time draws the boundary shifted by the host's UTC offset. The checker forces TZ=EST5
(a fixed UTC-5, valid POSIX TZ for glibc and honoured by the Windows CRT, verified on both),
so the naive shift is deterministic and does not depend on the host zone. The oracle entries
sit up to 4h30 either side of the boundary, so any nonzero offset of an hour or more
misfiles some of them even on a host that ignored TZ.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "rotate.py"
    if not script.is_file():
        return False, "rotate.py was never written"
    as_of = (oracle_dir / "as_of.txt").read_text(encoding="utf-8").strip()

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "rotate.py")
        shutil.copyfile(oracle_dir / "app.log", stage / "app.log")
        completed = run_bounded(
            [sys.executable, "rotate.py", as_of],
            cwd=stage,
            timeout_s=60.0,
            env={"TZ": "EST5"},
        )
        if completed.returncode != 0:
            return False, f"rotate.py exited {completed.returncode}: {completed.stderr[-500:]}"
        archive_path = stage / "archive.log"
        if not archive_path.is_file():
            return False, "rotate.py ran but wrote no archive.log"
        archived = _lines(archive_path)
        remaining = _lines(stage / "app.log")

    expected_archive = _lines(oracle_dir / "expected_archive.txt")
    expected_app = _lines(oracle_dir / "expected_app.txt")
    if archived == expected_archive and remaining == expected_app:
        return True, f"{len(archived)} entries archived, {len(remaining)} kept"
    misfiled = sorted(
        set(archived) ^ set(expected_archive) | set(remaining) ^ set(expected_app)
    )
    return False, f"entries near the boundary are misfiled: {misfiled[:4]}"
