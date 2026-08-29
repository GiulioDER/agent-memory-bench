"""Run the produced registrar twice, which is what a retried deploy does.

The convention under test: the last step of a retried pipeline must be safe to run again. One run
of a blind append is correct and indistinguishable from the right answer; the second run is what
puts the same version in the register twice, and the sandbox never runs it twice.

Grading also checks the first run actually did something, so a script that refuses to write
anything is not rewarded for being trivially idempotent.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from harness.checker_run import run_bounded


def _lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "register.py"
    if not script.is_file():
        return False, "register.py was never written"

    version = (oracle_dir / "VERSION").read_text(encoding="utf-8").strip()
    before = _lines(oracle_dir / "releases.log")

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copyfile(script, stage / "register.py")
        shutil.copyfile(oracle_dir / "VERSION", stage / "VERSION")
        shutil.copyfile(oracle_dir / "releases.log", stage / "releases.log")

        first = run_bounded([sys.executable, "register.py"], cwd=stage, timeout_s=60.0)
        if first.returncode != 0:
            return False, f"register.py exited {first.returncode}: {first.stderr[-400:]}"
        after_first = _lines(stage / "releases.log")

        second = run_bounded([sys.executable, "register.py"], cwd=stage, timeout_s=60.0)
        if second.returncode != 0:
            return False, (
                f"register.py exited {second.returncode} on the SECOND run, so a retried deploy "
                f"fails outright: {second.stderr[-300:]}"
            )
        after_second = _lines(stage / "releases.log")

    if after_first == before:
        return False, f"the first run did not add {version!r} to releases.log"
    if version not in after_first:
        return False, f"releases.log does not contain {version!r} after the first run"
    for existing in before:
        if existing not in after_first:
            return False, f"the first run dropped the existing entry {existing!r}"

    if after_second != after_first:
        duplicated = [entry for entry in set(after_second) if after_second.count(entry) > 1]
        return False, (
            f"running it a second time changed releases.log, so a retried deploy corrupts the "
            f"register; duplicated {duplicated or after_second[-2:]}"
        )
    return True, f"added {version!r} once, and the retry left {len(after_second)} entries unchanged"
