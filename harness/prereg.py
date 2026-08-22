"""The preregistration guard: no measured run while the protocol is uncommitted.

An uncommitted preregistration has no timestamp anyone can trust, including yours. The run
scripts call :func:`assert_preregistered` before launching a single session; it refuses when
anything under ``preregistration/`` is untracked or modified, and it names the files.

This enforces only "nothing is uncommitted". It cannot verify that a record exists for the
question you are about to measure, and it says so rather than implying otherwise.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PREREG_DIR = "preregistration"


class PreregistrationDirty(RuntimeError):
    pass


def dirty_preregistration_files(repo_root: str | Path) -> list[str]:
    """Paths under ``preregistration/`` that are modified or untracked."""

    result = subprocess.run(
        ["git", "status", "--porcelain", "--", PREREG_DIR],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line[3:].strip() for line in result.stdout.splitlines() if line.strip()]


def assert_preregistered(repo_root: str | Path) -> None:
    """Refuse to measure while the preregistration directory is dirty."""

    dirty = dirty_preregistration_files(repo_root)
    if dirty:
        raise PreregistrationDirty(
            "refusing to start a measured run: uncommitted preregistration files "
            f"{dirty}. Commit them first; an uncommitted prediction has no timestamp "
            "anyone can trust. (This guard checks only cleanliness; it cannot confirm a "
            "record exists for YOUR question.)"
        )
