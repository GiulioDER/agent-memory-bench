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


def _oracle_defect(oracle_dir: Path) -> str | None:
    """Why this oracle could no longer tell the naive solution from the informed one, or None.

    Both the backup and what it is compared against are read from the staged tree, so an oracle
    with no dotfiles is self-consistent: a glob-based walk copies every file it can see, nothing
    is missing, and the verdict below claims "hidden ones included" over a tree that had none.
    An oracle with no files at all passes for the same reason, vacuously.

    See `tasks/ts-natural-order/checker.py::_oracle_defect` for why this fails closed with a
    verdict rather than raising.
    """

    project = oracle_dir / "project"
    if not project.is_dir():
        return f"{project} does not exist"
    files = [path for path in project.rglob("*") if path.is_file()]
    if not files:
        return f"{project} holds no files"
    hidden = [
        path.relative_to(project).as_posix()
        for path in files
        if any(part.startswith(".") for part in path.relative_to(project).parts)
    ]
    if not hidden:
        return (
            f"no file under {project.name}/ is hidden, so a glob-based walk copies everything "
            f"and produces a complete backup without the convention"
        )
    return None


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    defect = _oracle_defect(oracle_dir)
    if defect is not None:
        return False, f"oracle is not well formed: {defect}"

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
