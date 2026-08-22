"""Run the produced backup.py against an oracle project tree that contains dotfiles.

The convention under test: a backup includes hidden files. Every file in the oracle tree,
dotted or not, must land in backups/project/ with identical bytes; glob-based walks skip the
dotted ones and produce a backup that looks complete.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "backup.py"
    if not script.is_file():
        return False, "backup.py was never written"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "backup.py")
        shutil.copytree(oracle_dir / "project", stage / "project")
        completed = run_bounded([sys.executable, "backup.py"], cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, f"backup.py exited {completed.returncode}: {completed.stderr[-500:]}"
        backup_root = stage / "backups" / "project"
        if not backup_root.is_dir():
            return False, "backup.py ran but backups/project/ does not exist"

        source_root = stage / "project"
        missing = []
        differing = []
        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root)
            copied = backup_root / relative
            if not copied.is_file():
                missing.append(relative.as_posix())
            elif copied.read_bytes() != path.read_bytes():
                differing.append(relative.as_posix())

    if missing:
        return False, f"backup is missing files: {missing}"
    if differing:
        return False, f"backup corrupted files: {differing}"
    return True, "every file, hidden ones included, landed in the backup"
