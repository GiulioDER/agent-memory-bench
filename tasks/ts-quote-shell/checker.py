"""Run the produced deploy.sh against a release directory whose name contains spaces.

The governing fact: production release directories contain spaces, so every path in deploy
scripts is quoted. Unquoted expansions word-split; the script either dies or scatters files
into fragments of the intended path. Both count as failure here, and neither is visible in
the sandbox, whose paths are clean. Runs under Git Bash via harness.checker_run.run_bash.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness.checker_run import run_bash

TARGET = "prod root v2"

EXPECTED = (
    Path("app") / "main.py",
    Path("assets") / "logo.svg",
    Path("assets") / "css" / "site.css",
    Path("assets") / "fonts" / "inter.txt",
)


def check(workdir: Path, oracle_dir: Path) -> tuple[bool, str]:
    script = workdir / "deploy.sh"
    if not script.is_file():
        return False, "deploy.sh is gone"

    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        shutil.copytree(oracle_dir / "tree", stage, dirs_exist_ok=True)
        shutil.copyfile(script, stage / "deploy.sh")
        completed = run_bash("deploy.sh", TARGET, cwd=stage, timeout_s=60.0)
        if completed.returncode != 0:
            return False, (
                f"deploy.sh exited {completed.returncode} on a spaced release dir: "
                f"{completed.stderr[-400:]}"
            )
        release = stage / TARGET
        missing = [str(rel) for rel in EXPECTED if not (release / rel).is_file()]
        if missing:
            return False, f"missing under {TARGET!r}: {missing}"
        first_word = stage / TARGET.split()[0]
        if first_word.exists():
            return False, (
                f"word-splitting artefact {first_word.name!r} exists beside the release dir"
            )
    return True, f"full tree staged under the spaced release dir {TARGET!r}"
